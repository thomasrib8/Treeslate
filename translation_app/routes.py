from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, send_from_directory
import os
import threading
from .utils import (
    translate_docx_with_deepl,
    improve_translation,
    create_glossary,
    convert_excel_to_csv,
)
import logging

# Création du Blueprint
translation_bp = Blueprint("translation", __name__, template_folder="../templates/translation")

# Configuration des logs
logger = logging.getLogger(__name__)

# Dictionnaire pour suivre le statut des traitements (utilisation d'un ID utilisateur statique)
STATIC_USER_ID = "static_user_id"
progress_store = {STATIC_USER_ID: {"status": "idle", "message": "Aucune tâche en cours.", "output_file_name": None}}

def get_user_progress():
    """
    Récupère ou initialise le statut de l'utilisateur statique.
    """
    return progress_store.setdefault(STATIC_USER_ID, {"status": "idle", "message": "Aucune tâche en cours.", "output_file_name": None})

def set_user_progress(status, message, output_file_name=None):
    """
    Met à jour le statut de l'utilisateur statique.
    """
    progress_store[STATIC_USER_ID] = {
        "status": status,
        "message": message,
        "output_file_name": output_file_name,
    }
    logger.debug(f"Progress store mis à jour : {progress_store[STATIC_USER_ID]}")

@translation_bp.route("/")
def index():
    logger.debug("Page principale (index) affichée.")
    return render_template("index.html")

@translation_bp.route("/processing")
def processing():
    """
    Affiche la page de traitement.
    """
    progress = get_user_progress()
    logger.debug(f"Accès à la page de traitement. Statut actuel : {progress}")
    return render_template("processing.html")

@translation_bp.route("/done")
def done():
    """
    Affiche la page de fin lorsque le traitement est terminé.
    """
    filename = request.args.get("filename", "improved_output.docx")
    return render_template("done.html", output_file_name=filename)

@translation_bp.route("/downloads/<filename>")
def download_file(filename):
    """
    Permet le téléchargement du fichier généré.
    """
    download_path = current_app.config["DOWNLOAD_FOLDER"]
    file_path = os.path.join(download_path, filename)
    logger.debug(f"Demande de téléchargement pour : {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"Fichier non trouvé : {file_path}")
        return "File not found", 404

    return send_from_directory(download_path, filename, as_attachment=True)

@translation_bp.route("/check_status")
def check_status():
    """
    Vérifie le statut du traitement.
    """
    progress = get_user_progress()
    logger.debug(f"Statut actuel renvoyé : {progress}")
    return jsonify(progress)

@translation_bp.route("/process", methods=["POST"])
def process():
    """
    Démarre le traitement en arrière-plan.
    """
    app_context = current_app._get_current_object()

    def background_process(app_context, input_path, final_output_path, **kwargs):
        with app_context.app_context():
            try:
                set_user_progress("in_progress", "Traitement en cours...")
                logger.debug("Début du traitement en arrière-plan.")

                # Création du glossaire si un fichier est fourni
                glossary_id = None
                if kwargs.get("glossary_csv_path"):
                    logger.debug(f"Création du glossaire avec le fichier : {kwargs['glossary_csv_path']}")
                    glossary_id = create_glossary(
                        api_key=app_context.config["DEEPL_API_KEY"],
                        name="MyGlossary",
                        source_lang=kwargs["source_language"],
                        target_lang=kwargs["target_language"],
                        glossary_path=kwargs["glossary_csv_path"],
                    )

                # Étape 1 : Traduction avec DeepL
                translated_output_path = os.path.join(app_context.config["UPLOAD_FOLDER"], "translated.docx")
                translate_docx_with_deepl(
                    api_key=app_context.config["DEEPL_API_KEY"],
                    input_file_path=input_path,
                    output_file_path=translated_output_path,
                    target_language=kwargs["target_language"],
                    source_language=kwargs["source_language"],
                    glossary_id=glossary_id,
                )

                # Étape 2 : Amélioration avec GPT
                improve_translation(
                    input_file=translated_output_path,
                    glossary_path=kwargs.get("glossary_gpt_path"),
                    output_file=final_output_path,
                    language_level=kwargs["language_level"],
                    source_language=kwargs["source_language"],
                    target_language=kwargs["target_language"],
                    group_size=kwargs["group_size"],
                    model=kwargs["gpt_model"],
                )

                # Mise à jour du statut final
                set_user_progress("done", "Traitement terminé avec succès.", output_file_name=os.path.basename(final_output_path))
                logger.debug("Traitement terminé avec succès.")

            except Exception as e:
                set_user_progress("error", f"Une erreur est survenue : {str(e)}")
                logger.error(f"Erreur dans le traitement : {e}")

    # Gestion des fichiers téléchargés
    input_file = request.files["input_file"]
    input_path = os.path.join(current_app.config["UPLOAD_FOLDER"], input_file.filename)
    input_file.save(input_path)

    glossary_csv = request.files.get("glossary_csv")
    glossary_csv_path = None
    if glossary_csv:
        glossary_csv_path = os.path.join(current_app.config["UPLOAD_FOLDER"], glossary_csv.filename)
        glossary_csv.save(glossary_csv_path)
        if glossary_csv_path.endswith(".xlsx"):
            glossary_csv_path = convert_excel_to_csv(glossary_csv_path, glossary_csv_path.replace(".xlsx", ".csv"))

    glossary_gpt = request.files.get("glossary_gpt")
    glossary_gpt_path = None
    if glossary_gpt:
        glossary_gpt_path = os.path.join(current_app.config["UPLOAD_FOLDER"], glossary_gpt.filename)
        glossary_gpt.save(glossary_gpt_path)

    output_file_name = request.form.get("output_file_name", "improved_output.docx")
    final_output_path = os.path.join(current_app.config["DOWNLOAD_FOLDER"], output_file_name)

    # Démarrage du thread de traitement
    thread_args = {
        "glossary_csv_path": glossary_csv_path,
        "glossary_gpt_path": glossary_gpt_path,
        "source_language": request.form["source_language"],
        "target_language": request.form["target_language"],
        "language_level": request.form["language_level"],
        "group_size": int(request.form["group_size"]),
        "gpt_model": request.form["gpt_model"],
    }

    threading.Thread(target=background_process, args=(app_context, input_path, final_output_path), kwargs=thread_args).start()

    return redirect(url_for("translation.processing"))

@translation_bp.route("/error")
def error():
    """
    Affiche une page d'erreur en cas de problème.
    """
    progress = get_user_progress()
    error_message = progress.get("message", "Une erreur est survenue.")
    return render_template("error.html", error_message=error_message)
