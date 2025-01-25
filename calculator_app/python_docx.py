import docx
from datetime import timedelta

def get_docx_stats(file_path):
    doc = docx.Document(file_path)
    words = 0
    characters = 0
    paragraphs = len(doc.paragraphs)
    for paragraph in doc.paragraphs:
        words += len(paragraph.text.split())
        characters += len(paragraph.text)
    pages = len(doc.sections)  # Approximating pages as sections
    return words, characters, pages, paragraphs

def calculate_translation_time(words, paragraphs, group_size):
    step1_time = words * 0.00156  # Time for step 1
    group_time_map = {
        1: 1.5, 2: 1.8, 3: 2.5, 4: 3.0, 5: 3.2,
        6: 3.3, 7: 3.5, 8: 4.0, 9: 3.8, 10: 4.0
    }
    step2_time = paragraphs * group_time_map.get(group_size, 3.0)  # Default to 3.0 if invalid group_size
    total_time_sec = step1_time + step2_time
    return timedelta(seconds=total_time_sec), total_time_sec

def calculate_translation_cost(words, characters, translation_time_min):
    tokens = words * 2
    step1_cost = tokens * 0.0000015  # Token cost
    step2_cost = characters * 0.000021  # Deep cost
    step3_cost = translation_time_min * 0.005161  # Web app cost
    return step1_cost + step2_cost + step3_cost

def calculate_review_cost(words, reviewer_choice):
    if reviewer_choice == "TOBY":
        return words * 0.025
    elif reviewer_choice == "TOBY+MIKE":
        return pages * 0.025
    elif reviewer_choice == "MIKE":
        return 0
    else:
        raise ValueError("Invalid reviewer choice")

def main():
    # Input file path
    file_path = input("Enter the path to the .docx file: ")
    words, characters, pages, paragraphs = get_docx_stats(file_path)
    
    # Display document stats
    print(f"Words: {words}")
    print(f"Characters: {characters}")
    print(f"Pages: {pages}")
    print(f"Paragraphs: {paragraphs}")
    
    # Input group size
    group_size = int(input("Enter the group size (1-10): "))
    translation_time, translation_time_sec = calculate_translation_time(words, paragraphs, group_size)
    translation_time_min = translation_time_sec / 60
    
    # Display translation time
    print(f"Translation time: {str(translation_time)}")
    
    # Calculate and display translation cost
    translation_cost = calculate_translation_cost(words, characters, translation_time_min)
    print(f"Translation cost: ${translation_cost:.6f}")
    
    # Input reviewer choice
    reviewer_choice = input("Enter the reviewer choice (TOBY, TOBY+MIKE, MIKE): ").upper()
    review_cost = calculate_review_cost(pages, reviewer_choice)
    
    # Display review cost
    print(f"Review cost: ${review_cost:.2f}")
    
    # Calculate and display total cost
    total_cost = translation_cost + review_cost
    print(f"Total cost: ${total_cost:.6f}")

if __name__ == "__main__":
    main()
