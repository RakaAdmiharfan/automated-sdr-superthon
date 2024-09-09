from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from .forms import UploadFileForm
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
import openai
from django.conf import settings
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt

# Set your OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

# Function to read PDF text
def read_pdf(file_path):
    with open(file_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        pdf_text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                pdf_text += page_text + " "
        return pdf_text

# Function to perform OCR extraction if PDF text can't be extracted
def ocr_extract_text(pdf_path):
    pages = convert_from_path(pdf_path, 300)
    ocr_text = ""
    for page in pages:
        page_text = pytesseract.image_to_string(page, lang='eng')
        ocr_text += page_text + " "
    return ocr_text

# Function to extract keywords using GPT-3
def extract_keywords_with_openai(text):
    prompt = f"Extract important keywords from the following text:\n\n{text}\n\nList the keywords separated by commas."
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    keywords = response.choices[0].message['content'].strip()
    return [keyword.strip() for keyword in keywords.split(',')]

# Function to check if keywords exist in the target PDF
def check_keywords_with_openai(text, keywords):
    summary = []
    lines = text.splitlines()
    for keyword in keywords:
        found = False
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                summary.append(f"Application: Pass - '{keyword}' found on line {i+1}: {line.strip()}")
                found = True
                break
        if not found:
            summary.append(f"Application: Fail - '{keyword}' not found")
    return "\n".join(summary)

# Function to summarize text using GPT-3
def ask_gpt_summary(text):
    prompt = (
        "You have extracted the text from a PDF document. Based on the text provided below, please summarize the content in one paragraph:\n\n"
        f"{text}\n\n"
        "Provide a concise summary."
    )
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )
    summary = response.choices[0].message['content'].strip()
    return summary

# Function to handle conversation with OpenAI based on history
def ask_gpt_question(conversation_history):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
            max_tokens=500
        )
        print(response)  # Log the entire response
        if response.choices and response.choices[0].message:
            return response.choices[0].message['content'].strip()
        else:
            return "I'm sorry, I couldn't process your request. Please try again."
    except Exception as e:
        return f"Error: {str(e)}"


@csrf_exempt
def upload_view(request):
    if request.method == 'POST':
        if 'conversation_history' in request.POST:
            try:
                # Retrieve the conversation history from the request
                conversation_history = request.POST.get('conversation_history', '[]')
                print(f"Received conversation_history: {conversation_history}")  # Debugging line

                # Parse the conversation history
                try:
                    conversation_history = json.loads(conversation_history)
                except json.JSONDecodeError as e:
                    print(f"JSON Decode Error: {str(e)}")  # Debugging line
                    return JsonResponse({'error': 'Invalid JSON format'}, status=400)

                # Call the GPT function to get a response
                gpt_response = ask_gpt_question(conversation_history)
                
                # Add GPT response to conversation history
                conversation_history.append({'role': 'system', 'content': gpt_response})

                # Return the updated conversation history
                response = {
                    'conversation_history': conversation_history
                }
                return JsonResponse(response)

            except Exception as e:
                print(f"Error: {str(e)}")  # Debugging line
                return JsonResponse({'error': str(e)}, status=500)

        else:
            # Handle file upload
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                # Handle file uploads
                standard_pdf = request.FILES['standard_pdf']
                target_pdf = request.FILES['target_pdf']
                fs = FileSystemStorage()
                #SAMPAI SINI ----
                # Save the uploaded files
                standard_pdf_path = fs.save(standard_pdf.name, standard_pdf)
                target_pdf_path = fs.save(target_pdf.name, target_pdf)

                # Generate URLs for the PDFs
                standard_pdf_url = fs.url(standard_pdf_path)
                target_pdf_url = fs.url(target_pdf_path)
                
                print(standard_pdf_url)

                # Process the PDFs
                standard_text = read_pdf(fs.path(standard_pdf_path))
                if not standard_text.strip():
                    standard_text = ocr_extract_text(fs.path(standard_pdf_path))

                target_text = read_pdf(fs.path(target_pdf_path))
                if not target_text.strip():
                    target_text = ocr_extract_text(fs.path(target_pdf_path))

                # Extract keywords from the standard PDF
                standard_keywords = extract_keywords_with_openai(standard_text)

                # Check for keywords in the target PDF
                results = check_keywords_with_openai(target_text, standard_keywords)

                # Generate summary of the standard PDF
                summary = ask_gpt_summary(standard_text)

                # Create conversation history
                conversation_history = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "system", "content": f"I have extracted text from a PDF document and here are the extracted keywords: {str(standard_keywords)}"},
                    {"role": "system", "content": f"Here are the keyword check results: {results}"},
                    {"role": "system", "content": f"Here is a summary of the document: {summary}"}
                ]

                # Check for AJAX request
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'standard_pdf_url': standard_pdf_url,
                        'target_pdf_url': target_pdf_url,
                        'standard_text': standard_text,
                        'target_text': target_text,
                        'standard_keywords': standard_keywords,
                        'results': results,
                        'summary': summary,
                        'conversation_history': conversation_history
                    })

                # Render the results in the template for non-AJAX request
                return render(request, 'polls/result.html', {
                    'standard_pdf_url': standard_pdf_url,
                    'target_pdf_url': target_pdf_url,
                    'standard_text': standard_text,
                    'target_text': target_text,
                    'standard_keywords': standard_keywords,
                    'results': results,
                    'summary': summary,
                    'conversation_history': conversation_history,
                })

    else:
        form = UploadFileForm()
    return render(request, 'polls/upload.html', {'form': form})

def results_view(request):
    # Placeholder view for results
    return render(request, 'polls/result.html')




