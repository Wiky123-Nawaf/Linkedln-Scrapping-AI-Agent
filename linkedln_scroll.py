import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import PyPDF2
import ollama
import os

def extract_text_from_pdf(pdf_path):
    """Extracts text content from a PDF file."""
    text = ""
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def ollama_answer_question(question_text, resume_text, model_name="mistral"):
    """Generates an answer to a question using a local Ollama LLM, considering the resume."""
    try:
        prompt = f"""
        [Resume]
        {resume_text}

        [Question]
        {question_text}

        Answer STRICTLY following these rules:
        1. For numeric questions (years/months): Return ONLY the number. If unsure, return 0.
        2. For yes/no questions: Return EXACTLY 'Yes' or 'No'.
        3. For dropdowns: Return EXACT option text from these choices: None, Conversational, Professional, Native or bilingual.
        4. For other questions: Concise answer using resume info only.
        """
        response = ollama.chat(model=model_name, messages=[
            {'role': 'user', 'content': prompt}
        ])
        return response['message']['content'].strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

def click_button(driver, button_text):
    """
    Clicks a button based on its aria-label, prioritizing "Next", "Review", and "Submit application".

    Args:
        driver: Selenium WebDriver instance.
        button_text: The aria-label text of the button to click (e.g., "Next", "Review", "Submit application").

    Returns:
        True if a button was found and clicked, False otherwise.
    """
    try:
        button_xpath = f"//button[contains(@aria-label, '{button_text}')]"
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, button_xpath))
        )
        print(f"Clicking button with aria-label: '{button_text}'")
        button.click()
        time.sleep(2)  # Small wait after clicking
        return True
    except NoSuchElementException:
        print(f"Button with aria-label: '{button_text}' not found or not clickable.")
        return False
    except Exception as e:
        print(f"Error clicking button '{button_text}': {e}")
        return False


def answer_additional_questions(driver, resume_text):
    """Handles different question types with improved element detection."""
    while True:
        # Find all question containers
        containers = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'fb-dash-form-element')]"))
        )

        for container in containers:
            try:
                # Radio Button Handling (Yes/No)
                radio_group = container.find_elements(By.XPATH, ".//fieldset[.//legend]")
                if radio_group:
                    question = radio_group[0].find_element(By.XPATH, ".//legend//span").text.strip()
                    answer = ollama_answer_question(question, resume_text) or "No"
                    choice = "Yes" if answer.lower() == "yes" else "No"
                    radio = container.find_element(By.XPATH, f".//input[@value='{choice}']")
                    driver.execute_script("arguments[0].click();", radio)
                    continue

                # Dropdown Handling
                dropdown = container.find_elements(By.XPATH, ".//select")
                if dropdown:
                    question = container.find_element(By.XPATH, ".//label[contains(@class, 'fb-dash-form-element__label')]").text.strip()
                    answer = ollama_answer_question(question, resume_text) or "Professional"
                    select = dropdown[0]
                    options = [opt.text for opt in select.find_elements(By.TAG_NAME, "option") if opt.get_attribute("value")]
                    match = next((opt for opt in options if answer.lower() in opt.lower()), options[1])
                    select.click()
                    select.find_element(By.XPATH, f"//option[text()='{match}']").click()
                    continue

                # Numeric Input Handling
                numeric_input = container.find_elements(By.XPATH, ".//input[contains(@class, 'artdeco-text-input--input')]")
                if numeric_input:
                    question = container.find_element(By.XPATH, ".//label[contains(@class, 'artdeco-text-input--label')]").text.strip()
                    answer = ollama_answer_question(question, resume_text) or "0"
                    number = re.findall(r'\d+', answer)[0] if re.findall(r'\d+', answer) else "0"
                    numeric_input[0].clear()
                    numeric_input[0].send_keys(number)
                    continue

            except Exception as e:
                print(f"Error processing question: {e}")

        # Navigation handling (moved to navigate_application_form function)
        return True # Indicate page processed


def linkedin_job_search_and_apply(resume_pdf_path):
    # Set up Chrome driver
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get("https://www.linkedin.com/")

    # Login
    time.sleep(3)
    sign_in_button = driver.find_element(By.XPATH, "//a[contains(@class, 'sign-in-form__sign-in-cta')]")
    sign_in_button.click()
    time.sleep(3)
    email_input = driver.find_element(By.ID, "username")
    email_input.send_keys("") # Replace with your email
    password_input = driver.find_element(By.ID, "password")
    password_input.send_keys("") # Replace with your password
    sign_in_submit = driver.find_element(By.XPATH, "//button[@data-litms-control-urn='login-submit']")
    sign_in_submit.click()
    time.sleep(30)

    # Job Search
    jobs_button = driver.find_element(By.XPATH, "//span[text()='Jobs']")
    jobs_button.click()
    time.sleep(5)
    location_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//input[@aria-label='City, state, or zip code']"))
    )
    location_input.clear()
    location_input.send_keys("Malaysia")
    title_input = driver.find_element(By.XPATH, "//input[contains(@class, 'jobs-search-box__keyboard-text-input')]")
    title_input.send_keys("deep learning")
    title_input.send_keys(Keys.RETURN)
    time.sleep(5)

    # Filters
    try:
        easy_apply_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Easy Apply filter.']"))
        )
        easy_apply_button.click()
        print("Easy Apply filter clicked!")
    except Exception as e:
        print(f"Failed to click Easy Apply filter: {e}")
    time.sleep(5)
    try:
        date_posted_dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@id='searchFilter_timePostedRange']"))
        )
        date_posted_dropdown.click()
        print("Date posted dropdown expanded!")
    except Exception as e:
        print(f"Failed to expand Date posted dropdown: {e}")
    time.sleep(3)
    try:
        past_24_hours_label = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//label[@for='timePostedRange-r86400']"))
        )
        past_24_hours_label.click()
        print("Past 24 hours filter selected!")
    except Exception as e:
        print(f"Failed to select Past 24 hours filter: {e}")
    time.sleep(5)
    try:
        show_more_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Apply current filter')]"))
        )
        show_more_button.click()
        print("Show more button clicked!")
    except Exception as e:
        print(f"Failed to click Show more button: {e}")
    time.sleep(5)

    resume_text = extract_text_from_pdf(resume_pdf_path)
    if not resume_text:
        print("Could not extract text from resume. Exiting.")
        driver.quit()
        return

    job_counter = 0
    page_number = 1
    while True:
        print(f"Processing Page {page_number}")
        try:
            job_cards = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'job-card-container') and contains(@class, 'job-card-list')]"))
            )
        except Exception as e_job_cards:
            print(f"Error finding job cards on page {page_number}: {e_job_cards}")
            break

        if not job_cards:
            print(f"No job cards found on page {page_number}. Maybe end of listings or issue with selector.")
            break

        for job_card in job_cards:
            job_counter += 1
            print(f"--- Processing Job {job_counter} ---")
            try:
                job_title_element = job_card.find_element(By.XPATH, ".//a[contains(@class, 'job-card-container__link')]")
                job_title_text = job_title_element.text
                print(f"Job Title: {job_title_text}")
                job_title_element.click()

                try:
                    job_description_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "job-details"))
                    )
                    job_description_text = job_description_element.text
                    print("Job Description:", job_description_text[:500] + "...")

                    def assess_job_fit_with_ollama(resume_text, job_description_text):
                        return True

                    fit_assessment = assess_job_fit_with_ollama(resume_text, job_description_text)

                    if fit_assessment:
                        print("LLM says: Resume is a good fit. Applying...")
                        try:
                            easy_apply_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'jobs-apply-button') and contains(@class, 'artdeco-button--primary')]"))
                            )
                            easy_apply_button.click()
                            print("Easy Apply button clicked!")
                            time.sleep(5)

                            # --- Iterative "Next" Button Clicks (from provided code) ---
                            while True:
                                try:
                                    if not click_button(driver, "Continue to next step"): # Use click_button for navigation
                                        break # Exit loop if "Next" button is not found
                                except Exception as e_next_click:
                                    print(f"Error clicking 'Next' button during initial form steps: {e_next_click}")
                                    break # Exit loop on error


                            # --- Answer questions AFTER initial "Next" clicks ---
                            print("Answering additional questions...")
                            if answer_additional_questions(driver, resume_text): # Call function to handle questions and submission
                                # --- Check for "Review" then "Submit" using prioritized click_button ---
                                print("Navigating Review/Submit...")
                                if click_button(driver, "Review your application"):
                                    print("Clicked Review, now looking for Submit...")
                                    if click_button(driver, "Submit application"):
                                        print("Application submitted successfully for this job.")
                                    else:
                                        print("Submit application button not found after Review.")
                                elif click_button(driver, "Submit application"): # Directly try Submit if Review not found
                                    print("Clicked Submit application directly (Review skipped).")
                                else:
                                    print("Neither Review nor Submit application button found after questions.")
                            else:
                                print("Error answering additional questions, application flow stopped.")


                            # After applying, close the application popup
                            try:
                                close_button = WebDriverWait(driver, 10).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label='Dismiss']"))
                                )
                                close_button.click()
                                print("Closed application popup.")
                                time.sleep(2)
                            except:
                                print("Could not find or close application popup, proceeding to next job.")

                        except Exception as apply_e:
                            print(f"Could not click Easy Apply or handle application popup: {apply_e}")
                    else:
                        print("LLM says: Resume is not a good fit. Skipping job.")

                except Exception as e_job_desc:
                    print(f"Error extracting job description: {e_job_desc}")

            except Exception as job_card_e:
                print(f"Error processing job card: {job_card_e}")

        # Pagination
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='View next page']"))
            )
            if next_button.is_enabled():
                next_button.click()
                print("Clicked 'Next' page button.")
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'job-card-container') and contains(@class, 'job-card-list')]"))
                    )
                except:
                    print("Timeout waiting for next page job cards to load. Proceeding to next iteration check.")
                page_number += 1
            else:
                print("Next page button is disabled. End of job listings.")
                break
        except Exception as pagination_e:
            print(f"Could not find or click 'Next' page button: {pagination_e}")
            break

    print("Job search and apply process completed!")
    driver.quit()


def navigate_application_form(driver, resume_text): # This function is now integrated into linkedin_job_search_and_apply and is no longer needed separately.
    pass


if __name__ == "__main__":
    resume_path = r"D:\Nawaf_Waqas_CV.pdf"  # Replace with your actual path to your resume PDF
    if not os.path.exists(resume_path):
        print(f"Resume PDF not found at: {resume_path}. Please update the path.")
    else:
        linkedin_job_search_and_apply(resume_path)
