import streamlit as st
import google.generativeai as genai
import PyPDF2
import docx
import json
from googletrans import Translator
import time

# Configure Gemini Pro
GEMINI_API_KEY = "AIzaSyAZ11Tinh63Rs1F0yWniCvNG33Q00xag1o"  # Replace with your actual API key
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Initialize Google Translator
translator = Translator()

# Supported languages
LANGUAGES = {
    "English": "en",
    "Telugu": "te",
    "Tamil": "ta",
    "Malayalam": "ml",
    "Kannada": "kn",
    "Hindi": "hi",
    "Bengali": "bn",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Urdu": "ur",
    "Punjabi": "pa",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Chinese": "zh-cn",
    "Japanese": "ja",
    "Korean": "ko"
}

def translate_text(text, target_lang):
    """Translate text using Google Translate."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if target_lang == "en":  # No translation needed for English
                return text
            translation = translator.translate(text, dest=target_lang)
            return translation.text
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                st.error(f"Translation error: {str(e)}")
                return text
            time.sleep(1)  # Wait before retrying

def translate_questions(questions, target_lang):
    """Translate all parts of the questions dictionary."""
    translated_questions = []
    for q in questions:
        translated_q = {
            "question": translate_text(q["question"], target_lang),
            "correct_answer": translate_text(q["correct_answer"], target_lang),
            "explanation": translate_text(q["explanation"], target_lang)
        }
        if "options" in q:
            translated_q["options"] = [translate_text(opt, target_lang) for opt in q["options"]]
        translated_questions.append(translated_q)
    return translated_questions

def read_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def read_docx(file):
    doc = docx.Document(file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def read_txt(file):
    return file.getvalue().decode("utf-8")

import re

def sanitize_json(raw_response):
    """Enhanced JSON sanitization function."""
    # Remove any markdown code block indicators
    cleaned = re.sub(r'```json\s*|\s*```', '', raw_response)
    
    # Remove any leading/trailing whitespace
    cleaned = cleaned.strip()
    
    # Ensure proper JSON structure
    if not cleaned.startswith('{'):
        cleaned = '{' + cleaned
    if not cleaned.endswith('}'):
        cleaned = cleaned + '}'
        
    # Replace any unescaped newlines within strings
    cleaned = re.sub(r'(?<!\\)\n', ' ', cleaned)
    
    # Fix any missing commas between objects in arrays
    cleaned = re.sub(r'}\s*{', '},{', cleaned)
    
    # Handle any unescaped quotes within strings
    cleaned = re.sub(r'(?<!\\)"(?=[^"]*"(?:[^"]*"[^"]*")*[^"]*$)', '\\"', cleaned)
    
    return cleaned

def generate_questions(text, question_type, num_questions, difficulty):
    """Generate questions using Gemini Pro with improved handling of different question types."""
    
    # Define question type specific prompts
    type_specific_prompts = {
        "Multiple Choice": """
        Use exactly this JSON structure:
        {
            "questions": [
                {
                    "question": "Question text here?",
                    "options": [
                        "Correct answer here",
                        "Incorrect option 1",
                        "Incorrect option 2",
                        "Incorrect option 3"
                    ],
                    "correct_answer": "Correct answer here",
                    "explanation": "Explanation here"
                }
            ]
        }
        Requirements:
        1. Each question must have exactly 4 options
        2. The correct_answer must match the first option exactly
        """,
        
        "True/False": """
        Use exactly this JSON structure:
        {
            "questions": [
                {
                    "question": "True or False: Statement here?",
                    "correct_answer": "True",
                    "explanation": "Explanation here"
                }
            ]
        }
        Requirements:
        1. Each question must start with 'True or False:'
        2. The correct_answer must be either 'True' or 'False'
        """,
        
        "Short Answer": """
        Use exactly this JSON structure:
        {
            "questions": [
                {
                    "question": "Short answer question here?",
                    "correct_answer": "Brief, specific answer here",
                    "explanation": "Detailed explanation here"
                }
            ]
        }
        Requirements:
        1. Questions should require brief, specific answers
        2. Correct answers should be 1-3 words when possible
        """,
        
        "Fill-in-the-Blanks": """
        Use exactly this JSON structure:
        {
            "questions": [
                {
                    "question": "Sentence with _____ to fill in.",
                    "correct_answer": "word or phrase",
                    "explanation": "Explanation here"
                }
            ]
        }
        Requirements:
        1. Each question must have exactly one blank marked with _____
        2. The correct_answer must fit grammatically in the blank
        """
    }
    
    base_prompt = f"""
    Generate {num_questions} {difficulty}-level {question_type} educational questions about the following text.
    Return the response in valid JSON format with no markdown formatting.
    
    Text: {text}
    
    {type_specific_prompts[question_type]}
    """
    
    try:
        # Generate content
        response = model.generate_content(
            base_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                top_p=0.8,
                top_k=40,
                candidate_count=1,
                max_output_tokens=2048,
            ),
        )
        
        raw_response = response.text if hasattr(response, 'text') else None
        if not raw_response:
            raise ValueError("No response received from the model.")
        
        # Parse and validate JSON
        try:
            questions_data = json.loads(raw_response)
        except json.JSONDecodeError:
            sanitized = sanitize_json(raw_response)
            questions_data = json.loads(sanitized)
        
        # Validate structure and question type specific requirements
        if not isinstance(questions_data, dict) or 'questions' not in questions_data:
            raise ValueError("Invalid response format: missing 'questions' key")
        
        # Type-specific validation
        for q in questions_data['questions']:
            if question_type == "Multiple Choice":
                validate_multiple_choice(q)
            elif question_type == "True/False":
                validate_true_false(q)
            elif question_type == "Fill-in-the-Blanks":
                validate_fill_blanks(q)
            elif question_type == "Short Answer":
                validate_short_answer(q)
        
        return questions_data
        
    except Exception as e:
        st.error(f"Error generating questions: {str(e)}")
        return None

def validate_multiple_choice(question):
    """Validate multiple choice question structure."""
    if 'options' not in question or not isinstance(question['options'], list):
        raise ValueError("Multiple choice question missing options array")
    if len(question['options']) != 4:
        raise ValueError("Multiple choice questions must have exactly 4 options")
    if question['correct_answer'] != question['options'][0]:
        question['correct_answer'] = question['options'][0]

def validate_true_false(question):
    """Validate true/false question structure."""
    if not question['question'].lower().startswith("true or false:"):
        question['question'] = f"True or False: {question['question']}"
    if question['correct_answer'].lower() not in ['true', 'false']:
        raise ValueError("True/False questions must have 'True' or 'False' as correct answer")

def validate_fill_blanks(question):
    """Validate fill-in-the-blanks question structure."""
    if '_____' not in question['question']:
        raise ValueError("Fill-in-the-blanks questions must contain '_____'")

def validate_short_answer(question):
    """Validate short answer question structure."""
    if len(question['correct_answer'].split()) > 10:
        raise ValueError("Short answer correct answer should be concise")

def take_test(questions, question_type):
    """Display interactive test with question type specific handling."""
    score = 0
    user_answers = []
    
    for i, q in enumerate(questions):
        st.write(f"### Question {i+1}")
        st.write(q["question"])
        
        # Question type specific input handling
        if question_type == "Multiple Choice":
            answer = st.radio(
                "Select your answer:",
                q["options"],
                key=f"q_{i}"
            )
        elif question_type == "True/False":
            answer = st.radio(
                "Select your answer:",
                ["True", "False"],
                key=f"q_{i}"
            )
        elif question_type == "Fill-in-the-Blanks":
            answer = st.text_input(
                "Fill in the blank:",
                key=f"q_{i}"
            )
        else:  # Short Answer
            answer = st.text_input(
                "Your answer:",
                key=f"q_{i}"
            )
        
        user_answers.append({
            "question": q["question"],
            "user_answer": answer,
            "correct_answer": q["correct_answer"],
            "explanation": q["explanation"]
        })
    
    return user_answers


def display_questions(questions):
    """Display questions in a structured format."""
    for i, q in enumerate(questions):
        st.write(f"### Question {i+1}")
        st.write(q["question"])
        if "options" in q:
            for idx, option in enumerate(q["options"], 1):
                st.write(f"{idx}. {option}")
        st.write(f"**Correct Answer:** {q['correct_answer']}")
        st.write(f"**Explanation:** {q['explanation']}")
        st.write("---")



def main():
    st.title("AI Question Generator with Translation")
    st.write("Upload a document, generate questions, and learn in your preferred language!")

    # Initialize session state if not already initialized
    if 'questions' not in st.session_state:
        st.session_state.questions = None
    if 'generated' not in st.session_state:
        st.session_state.generated = False
    if 'mode' not in st.session_state:
        st.session_state.mode = None
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}
    if 'test_submitted' not in st.session_state:
        st.session_state.test_submitted = False

    uploaded_file = st.file_uploader("Upload a document (PDF, DOCX, or TXT)", type=['pdf', 'docx', 'txt'])
    
    if uploaded_file:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        try:
            # Read the file content
            if file_extension == 'pdf':
                text = read_pdf(uploaded_file)
            elif file_extension == 'docx':
                text = read_docx(uploaded_file)
            else:
                text = read_txt(uploaded_file)

            st.success("Document uploaded successfully!")

            # Input parameters
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                question_type = st.selectbox(
                    "Question Type", 
                    ["Multiple Choice", "True/False", "Short Answer", "Fill-in-the-Blanks"],
                    key="question_type"
                )
            with col2:
                difficulty = st.selectbox(
                    "Difficulty Level", 
                    ["Easy", "Medium", "Hard"],
                    key="difficulty"
                )
            with col3:
                num_questions = st.slider(
                    "Number of Questions", 
                    1, 10, 5,
                    key="num_questions"
                )
            with col4:
                lang = st.selectbox(
                    "Language", 
                    list(LANGUAGES.keys()),
                    key="language"
                )

            # Generate questions button
            if st.button("Generate Questions", key="generate_btn"):
                with st.spinner("Generating questions..."):
                    # Reset all previous state
                    st.session_state.questions = None
                    st.session_state.user_answers = {}
                    st.session_state.test_submitted = False
                    st.session_state.mode = None
                    
                    # Generate new questions
                    questions = generate_questions(text, question_type, num_questions, difficulty)
                    if questions:
                        st.session_state.questions = translate_questions(questions["questions"], LANGUAGES[lang])
                        st.session_state.generated = True
                        st.success("Questions generated successfully!")

            # Only show mode selection if questions are generated
            if st.session_state.questions is not None:
                st.write("---")
                st.write("### Select Mode")
                mode = st.radio(
                    "Choose how you want to use the generated questions:",
                    ["Study Mode", "Test Mode"],
                    key="mode_selector",
                    horizontal=True
                )
                
                # Display content based on selected mode
                if mode == "Study Mode":
                    display_study_mode()
                else:
                    display_interactive_test()

        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

def display_study_mode():
    """Display questions in study mode."""
    if not st.session_state.questions:
        return

    st.write("### Study Materials")
    st.info("📚 Review the questions, answers, and explanations below to prepare for the test.")

    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Question {i+1}", expanded=True):
            st.write("**Question:**")
            st.write(q["question"])
            
            if "options" in q and isinstance(q["options"], list):
                st.write("\n**Options:**")
                for opt in q["options"]:
                    if opt == q["correct_answer"]:
                        st.success(f"✅ {opt}")
                    else:
                        st.write(f"- {opt}")
            
            st.write("\n**Correct Answer:**")
            st.success(q["correct_answer"])
            
            st.write("\n**Explanation:**")
            st.info(q["explanation"])

def display_interactive_test():
    """Display questions in test mode."""
    if not st.session_state.questions:
        return

    st.write("### Test Mode")
    st.warning("⚠️ Select your answers carefully. You'll see the results after submitting.")

    # Create form for test submission
    with st.form(key='test_form'):
        for i, q in enumerate(st.session_state.questions):
            st.write(f"### Question {i+1}")
            st.write(q["question"])
            
            # Handle different question types
            if "options" in q and isinstance(q["options"], list):
                answer = st.radio(
                    "Select your answer:",
                    q["options"],
                    key=f"q_{i}",
                    index=None
                )
            elif q.get("question", "").lower().startswith("true or false"):
                answer = st.radio(
                    "Select your answer:",
                    ["True", "False"],
                    key=f"q_{i}",
                    index=None
                )
            else:
                answer = st.text_input(
                    "Your answer:",
                    key=f"q_{i}"
                )
            
            if answer:
                st.session_state.user_answers[i] = answer
        
        # Submit button
        submitted = st.form_submit_button("Submit Test")
        
    # Handle test submission
    if submitted:
        st.session_state.test_submitted = True
        display_results()


def display_results():
    """Display test results without refreshing."""
    st.write("---")
    st.write("### Test Results")
    
    score = 0
    total_questions = len(st.session_state.questions)
    
    # Calculate score
    for i, q in enumerate(st.session_state.questions):
        user_answer = st.session_state.user_answers.get(i, "").strip().lower()
        correct_answer = q["correct_answer"].strip().lower()
        if user_answer == correct_answer:
            score += 1

    # Display overall score
    percentage = (score / total_questions) * 100
    st.write(f"### Your Score: {score} out of {total_questions} ({percentage:.1f}%)")
    st.progress(percentage / 100)

    # Display individual question results
    for i, q in enumerate(st.session_state.questions):
        with st.expander(f"Question {i+1} Result", expanded=False):
            st.write(f"**Question:** {q['question']}")
            
            if "options" in q:
                st.write("**Options:**")
                for opt in q["options"]:
                    if opt == q["correct_answer"]:
                        st.success(f"✅ {opt} (Correct Answer)")
                    else:
                        st.write(f"- {opt}")
            
            user_answer = st.session_state.user_answers.get(i, "No answer provided")
            st.write(f"**Your Answer:** {user_answer}")
            st.write(f"**Correct Answer:** {q['correct_answer']}")
            st.write(f"**Explanation:** {q['explanation']}")
            
            if user_answer.strip().lower() == q['correct_answer'].strip().lower():
                st.success("Correct! ✅")
            else:
                st.error("Incorrect ❌")

    # Display final message and effects
    if score == total_questions:
        st.balloons()
        st.success("🎉 Perfect Score! Excellent work!")
    elif percentage >= 70:
        st.success(f"🌟 Good job! You scored {percentage:.1f}%")
    else:
        st.info(f"Keep practicing! You scored {percentage:.1f}%")

def reset_session_state():
    """Reset all session state variables."""
    st.session_state.generated = False
    st.session_state.questions = None
    st.session_state.user_answers = {}
    st.session_state.test_submitted = False
    st.session_state.mode = None

if __name__ == "__main__":
    main()