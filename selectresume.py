import streamlit as st
import zipfile
import os
import pandas as pd
import re
from langchain_groq import ChatGroq
import PyPDF2
import docx

# Title of the app
st.title("🦜🔗 Resume Analysis App")

# Add custom CSS for styling
st.markdown("""
    <style>
        .stTextInput>div>div>input {
            padding: 10px;
            font-size: 16px;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 15px 32px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 12px;
        }
        .stButton>button:hover {
            background-color: #45a049;
        }
        .stDownloadButton>button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            font-size: 16px;
            border-radius: 10px;
        }
        .stDownloadButton>button:hover {
            background-color: #0056b3;
        }
        .stDataFrame>div {
            margin-top: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# Add secret API key (replace with your actual environment variable key)
groq_api_key = st.secrets["GROQ_api_key"]

# Function to extract text from PDF
def extract_pdf_text(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to extract text from Word document (docx)
def extract_docx_text(docx_file):
    doc = docx.Document(docx_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Function to extract text from a plain text file
def extract_text_file(file):
    return file.read().decode("utf-8")

# Function to extract score from model response
def extract_score(response_content):
    try:
        match = re.search(r"(?i)rate this resume.*?(\d+)", response_content)
        if match:
            return int(match.group(1))
        else:
            return "No score found"
    except Exception as e:
        st.error(f"Error extracting score: {e}")
        return "Error"

# Function to score a resume
def score_resume(resume_text, job_description):
    try:
        llm = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name="mixtral-8x7b-32768")
        prompt = f"""
        Job Description:
        {job_description}

        Resume:
        {resume_text}

        Rate this resume from 0 to 100 based on its relevance to the job description. Provide reasoning.
        """
        response = llm.invoke(prompt)
        st.write("Raw Model Response:", response.content)  # Debug model response

        # Extract the score using the helper function
        score = extract_score(response.content)
        return score
    except Exception as e:
        st.error(f"Error scoring resume: {e}")
        return "Error"

# File upload section
uploaded_file = st.file_uploader("Upload a .zip file containing resumes", type=["zip"])

# Job description input
job_description = st.text_area("Paste the job description here", height=150)

# If a file is uploaded
if uploaded_file is not None:
    with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
        zip_ref.extractall("uploaded_resumes")  # Extract all files to a folder

    resumes = []
    for root, dirs, files in os.walk("uploaded_resumes"):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    text = extract_pdf_text(f)
                    resumes.append({"file_name": file, "text": text})
            elif file.endswith(".docx"):
                text = extract_docx_text(file_path)
                resumes.append({"file_name": file, "text": text})
            elif file.endswith(".txt"):
                with open(file_path, "rb") as f:
                    text = extract_text_file(f)
                    resumes.append({"file_name": file, "text": text})

    st.success(f"Uploaded and extracted {len(resumes)} resumes!")

    # Analyze resumes button
    if st.button("Analyze Resumes"):
        if not job_description:
            st.error("Please paste a job description before analyzing!")
        else:
            results = []
            for resume in resumes:
                score = score_resume(resume["text"], job_description)
                results.append({"file_name": resume["file_name"], "score": score})

            # Create a DataFrame from the results
            results_df = pd.DataFrame(results)

            # Display results in a table
            st.subheader("Analysis Results")
            st.dataframe(results_df)

            # Add a bar chart for scores
            st.subheader("Resume Score Visualization")
            if not results_df.empty and "score" in results_df:
                # Filter out non-numeric scores for visualization
                valid_scores_df = results_df[results_df["score"].apply(lambda x: isinstance(x, int))]

                if not valid_scores_df.empty:
                    st.bar_chart(data=valid_scores_df.set_index("file_name")["score"])
                else:
                    st.warning("No valid numeric scores to display in the chart.")
            else:
                st.warning("No data available for visualization.")

            # Add a download button for the results
            st.download_button(
                "Download Results",
                data=results_df.to_csv(index=False),
                file_name="resume_scores.csv",
                mime="text/csv",
            )

            # Create an email template based on the best scoring resume
            best_score = results_df["score"].max()
            best_resume = results_df[results_df["score"] == best_score].iloc[0]

            # Get the candidate name from the best resume file name
            candidate_name = best_resume["file_name"].split('.')[0]  # Assuming the file name is the candidate's name without the extension

            email_template = f"""
            Subject: Job Opportunity: {job_description.splitlines()[0]}

            Dear {candidate_name},

            I hope this email finds you well. I came across your resume for the position of [Job Title] at XYZ PVT LTD and was impressed by your qualifications and experience. Based on our analysis, your resume received a score of {best_score} out of 100, making you one of the most relevant candidates for this role.

            We would love to schedule an interview to further discuss how your skills align with the position. Please let us know your availability for the upcoming week.

            Looking forward to hearing from you.

            Best regards,
            [Your Name]
            [Your Contact Information]
            """

            st.subheader("Email Template for Best Candidate")
            st.text_area("Copy the email template below to send to the candidate:", email_template, height=250)

else:
    st.warning("Please upload a .zip file to get started!")
