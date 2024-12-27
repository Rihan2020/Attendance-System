import os
from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, date
from werkzeug.utils import secure_filename
import face_recognition
import cv2
import numpy as np


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///project.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Student(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    picture = db.Column(db.String(300), nullable=False)  # Store full path to the image
    date = db.Column(db.Date, default=date.today())
    
    def __repr__(self) -> str:
        return f"{self.sno} - {self.name}"

class Attendance(db.Model):
    sno = db.Column(db.Integer, primary_key=True)  # Unique ID for each attendance record
    student_id = db.Column(db.Integer, db.ForeignKey('student.sno'))  # Links to the Student table
    date_att = db.Column(db.DateTime, default=datetime.now)  # Date and time the student was marked as present
    status = db.Column(db.String(50), nullable=False)  # Status could be "Present", "Absent", etc.

# Set the folder to save images
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'picture' not in request.files:
        return 'No file part'

    file = request.files['picture']

    if file.filename == '':
        return 'No selected file'

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)  # Secure the filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        file.save(file_path)  # Save the image to /static/uploads/

        # Create a new student entry in the database
        new_student = Student(name=request.form['name'], picture=file_path)
        db.session.add(new_student)
        db.session.commit()

        return redirect('/')



@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form['name']
        picture = request.form['picture']

        stud = Student(name=name, picture=picture)
        db.session.add(stud)
        db.session.commit()

    allstud = Student.query.all()

    return render_template("index.html", allstud=allstud)

@app.route("/delete/<int:sno>")
def delete(sno):
    del_stud = Student.query.filter_by(sno=sno).first()
    db.session.delete(del_stud)
    db.session.commit()
    return redirect("/")


@app.route('/check', methods=["GET", "POST"])
def check_attn():
    if request.method == "POST":
        date = request.form.get('date')  # Use .get() to avoid KeyError
        if not date:
            return "Date is required!", 400  # Return an error message if no date is provided

        attendance_records = Attendance.query.filter(db.func.date(Attendance.date_att) == date).all()
        return render_template('check.html', attendance_records=attendance_records)
    return render_template('check.html', attendance_records=None)
    




@app.route('/mark', methods=['GET', 'POST'])
def mark_attendance():
    if request.method == 'POST':
        # Display message and redirect to the capture route
        return render_template('mark.html', message="Opening webcam to capture a face...")
    return render_template('mark.html')


@app.route('/capture', methods=['GET'])
def capture():

    """This function captures a live image and matches it against the saved images in the database to mark attendance."""
    
    # Step 1: Capture a live image from the webcam

    video_capture = cv2.VideoCapture(0)  # 0 for default webcam
    ret, frame = video_capture.read()  # Capture a single frame from the webcam
    video_capture.release()

    if not ret:
        print("Failed to capture image from webcam.")
        return "No image captured"
    
    # Save the captured image temporarily
    captured_image_path = 'static/uploads/live_image.jpg'
    cv2.imwrite(captured_image_path, frame)

    # Step 2: Load the captured image and encode the face
    live_image = face_recognition.load_image_file(captured_image_path)
    live_face_encodings = face_recognition.face_encodings(live_image)

    if len(live_face_encodings) == 0:
        print("No face detected in the captured image.")
        return "No face detected in the captured image"
    
    live_face_encoding = live_face_encodings[0]  # Get the first face detected

    # Step 3: Loop through all student images from the database
    students = Student.query.all()
    for student in students:
        stored_image_path = student.picture  # Path of the stored image

        if not os.path.exists(stored_image_path):
            print(f"Image not found for student {student.name} at {stored_image_path}")
            continue

        # Load the stored image and encode it
        stored_image = face_recognition.load_image_file(stored_image_path)
        stored_face_encodings = face_recognition.face_encodings(stored_image)
        
        if len(stored_face_encodings) == 0:
            print(f"No face detected in the stored image for student {student.name}")
            continue
        
        stored_face_encoding = stored_face_encodings[0]  # Get the first face detected

        # Step 4: Compare the face encodings (Match the live image with the stored image)
        match = face_recognition.compare_faces([stored_face_encoding], live_face_encoding)
        
        if match[0]:
            print(f"Face matched with {student.name} 🎉")
            
            # Mark attendance with required fields
            mark_studs = Attendance(student_id=student.name, status=True, date_att=datetime.now())
            db.session.add(mark_studs)
            db.session.commit()
            

            print(f"Attendance marked for {student.name} at {mark_studs.date_att}")
            return render_template('mark.html', mark_message=f"Attendance marked for {student.name} at {mark_studs.date_att}")



    print("No match found for the captured face.")
    return "No match found for the captured face", redirect('/mark')


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')