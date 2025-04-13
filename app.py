from flask import Flask, render_template, request, send_file, after_this_request
from fpdf import FPDF
import smtplib
from email.message import EmailMessage
from datetime import datetime
import os
import jwt  # Import pyjwt for decoding the token
from functools import wraps

app = Flask(__name__)

SECRET_KEY = "dc707ccf4dcd014384e0a0de7bdf2e437960164779561d86f9f24af245e6be0b"  # Define your secret key here

# Function to decode the JWT token
def decode_jwt(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token

@app.route("/")
def index():
    token = request.args.get("token")
    symptoms = request.args.get("symptoms", "")

    if token:
        # Decode the token to retrieve user information (including symptoms)
        decoded_data = decode_jwt(token)
        if decoded_data:
            # Fill the fields with decoded data if valid token
            name = decoded_data.get("name", "")
            email = decoded_data.get("email", "")
            phone = decoded_data.get("contact", "")
            allergies = decoded_data.get("allergies", "")
            symptoms = decoded_data.get("symptoms", symptoms)  # Use symptoms from token if available
        else:
            name = email = phone = allergies = symptoms = ""
            return render_template("report_form.html", error_message="Invalid or expired token.")
    else:
        # If no token provided, use empty values or form values
        name = email = phone = allergies = symptoms = ""
    
    return render_template("report_form.html", name=name, email=email, phone=phone, allergies=allergies, symptoms=symptoms)

@app.route("/generate_pdf", methods=["POST"])
def generate_pdf():
    temp_dir = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    
    pdf = None
    filename = None
    try:
        # Get form data safely
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        phone = request.form.get("phone", "")
        allergies = request.form.get("allergies", "")
        symptoms = request.form.get("symptoms", "")
        doctor_email = request.form.get("doctor_email", "")
        
        # Validate required fields
        if not all([name, email, doctor_email]):
            return render_template('report_form.html', error_message='Please fill in all required fields.')

        # Generate unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(temp_dir, f"{name.replace(' ', '_')}_{timestamp}_report.pdf")

        # Create PDF with modern design
        pdf = FPDF()
        pdf.add_page()
        
        # Header with stylized text
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(76, 175, 80)  # Green color
        pdf.cell(0, 15, 'Medical Report', 0, 1, 'C')
        
        # Subtitle
        pdf.set_font('Arial', 'I', 12)
        pdf.set_text_color(128, 128, 128)  # Gray color
        pdf.cell(0, 8, 'Patient Health Summary', 0, 1, 'C')
        pdf.ln(5)
        
        # Patient Info Section
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(33, 33, 33)  # Dark gray
        pdf.cell(0, 8, 'Patient Information', 0, 1, 'L')
        
        pdf.set_draw_color(76, 175, 80)  # Green color for lines
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        # Info content
        pdf.set_font('Arial', '', 12)
        pdf.set_text_color(66, 66, 66)  # Medium gray
        
        info_items = [
            ('Name', name),
            ('Email', email),
            ('Phone', phone),
            ('Allergies', allergies)
        ]
        
        for label, value in info_items:
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(30, 8, f'{label}:', 0, 0)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 8, value, 0, 1)
        
        # Symptoms Section
        pdf.ln(3)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(33, 33, 33)
        pdf.cell(0, 8, 'Symptoms', 0, 1, 'L')
        
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        pdf.set_font('Arial', '', 12)
        pdf.set_text_color(66, 66, 66)
        pdf.multi_cell(0, 8, symptoms)
        
        # Footer
        pdf.set_y(-15)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, f'Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        
        # Save PDF to a temporary file
        pdf.output(filename)

        # Email the PDF to the doctor
        email_result = send_email_to_doctor(filename, name, doctor_email)
        if isinstance(email_result, tuple) and not email_result[0]:
            error_msg = email_result[1]
            if os.path.exists(filename):
                os.remove(filename)
            return render_template('report_form.html', error_message=f'Failed to send email: {error_msg}')

        # Send the file to the user for download
        try:
            if not os.path.exists(filename):
                raise FileNotFoundError("PDF file was not generated properly")
                
            file_size = os.path.getsize(filename)
            if file_size == 0:
                raise ValueError("Generated PDF file is empty")
                
            return_data = send_file(
                filename,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=os.path.basename(filename)
            )
            
            # Let the file be sent before cleanup
            @after_this_request
            def cleanup(response):
                try:
                    if filename and os.path.exists(filename):
                        os.remove(filename)
                except Exception as e:
                    print(f"Error cleaning up temporary file: {e}")
                return response
                
            return return_data
            
        except Exception as e:
            if filename and os.path.exists(filename):
                os.remove(filename)
            return render_template('report_form.html', error_message=f'Failed to download PDF: {str(e)}')
    except Exception as e:
        if filename and os.path.exists(filename):
            os.remove(filename)
        return render_template('report_form.html', error_message=f'Failed to generate report: {str(e)}')

def send_email_to_doctor(filename, patient_name, doctor_email):
    try:
        # Email configuration
        sender_email = "jaydeep778899@gmail.com"
        app_password = "zoki eunp tysb iido"
        smtp_server = "smtp.gmail.com"
        smtp_port = 465

        # Validate email addresses
        if not all([sender_email, doctor_email]):
            raise ValueError("Sender and recipient email addresses are required")

        # Validate file existence and path
        if not os.path.exists(filename):
            raise FileNotFoundError(f"PDF file not found: {filename}")

        # Create email message
        msg = EmailMessage()
        msg['Subject'] = f"Patient Report - {patient_name}"
        msg['From'] = sender_email
        msg['To'] = doctor_email
        msg.set_content(f"Attached is the health report for {patient_name}.\n\nThis is an automated message from the Patient Report System.")

        # Attach PDF file
        try:
            with open(filename, "rb") as f:
                file_data = f.read()
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=filename
                )
        except Exception as e:
            raise Exception(f"Error attaching PDF file: {str(e)}")

        # Send email
        try:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as smtp:
                # Attempt login
                try:
                    smtp.login(sender_email, app_password)
                except smtplib.SMTPAuthenticationError:
                    raise Exception("Gmail authentication failed. Please verify your email and app password.")
                
                # Send message
                smtp.send_message(msg)
                print(f"Email sent successfully to {doctor_email}")
                return True

        except smtplib.SMTPConnectError:
            raise Exception(f"Failed to connect to SMTP server {smtp_server}. Please check your internet connection.")
        except smtplib.SMTPException as e:
            raise Exception(f"SMTP error occurred: {str(e)}")
        except TimeoutError:
            raise Exception("Connection timed out. Please check your internet connection.")
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error sending email: {error_msg}")
        return False, error_msg

if __name__ == "__main__":
    app.run(debug=True)
