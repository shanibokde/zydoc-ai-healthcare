from django.shortcuts import render,redirect,reverse,get_object_or_404, render
from . import forms,models
from django.db.models import Sum
from .models import Appointment
from django.utils import timezone
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect, JsonResponse
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required,user_passes_test
from datetime import datetime,timedelta,date
from django.conf import settings
from django.db.models import Q
import io
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.template import Context
from django.http import HttpResponse
# import datetime
import requests
import numpy as np
from sentence_transformers import SentenceTransformer
from django.db import connection
import psycopg2
from .chatbot_logic import MedicalChatbot
from django.http import JsonResponse
import json
from django.db import IntegrityError
from django.contrib import messages




def get_db_connection():
    return psycopg2.connect(
        dbname="medical_db",
        user="postgres",
        password="shani12",
        host="localhost",
        port="5432"
    )

try:
    embed_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    print(f"Error loading AI model: {e}")
    embed_model = None




def home_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')

    result = None
    today_str = date.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST' and 'symptom1' in request.POST:
        patient_name = request.POST.get('name')
        patient_mobile = request.POST.get('mobile') 
        
        request.session['temp_name'] = patient_name
        request.session['temp_mobile'] = patient_mobile
        request.session.modified = True 

        primary = request.POST.get('symptom1', '')
        follow_up = request.POST.get('symptom2', '')
        user_query = f"{primary} {follow_up}".strip()
        request.session['temp_symptoms'] = user_query 

        # ... (Your Embedding and DB search logic remains the same) ...
        try:
            query_vector = embed_model.encode(user_query).tolist()
        except:
            query_vector = None

        db_row = None
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            if query_vector:
                cur.execute("SELECT question, answer, medicine FROM medical_knowledge ORDER BY embedding <=> %s::vector LIMIT 1;", (query_vector,))
            else:
                cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
            db_row = cur.fetchone()
        finally:
            cur.close()
            conn.close()

        if db_row:
            matched_q, answer, medicine = db_row
            user_query_low = user_query.lower()
            
            # 1. CHECK STATUS FIRST
            is_emergency = any(word in user_query_low for word in ['broken', 'bleed', 'emergency', 'accident', 'chest pain'])
            is_consultation = any(word in user_query_low for word in ['week', 'month', 'years', 'long time', 'persistent'])

            if is_emergency:
                status = "emergency"
                final_doc_name = "Dr. vikas gupta" # ONLY for emergency
            elif is_consultation:
                status = "consultation"
                final_doc_name = "Dr. Sunil Rajendran" # DEFAULT for back pain/weeks
            else:
                status = "normal"
                final_doc_name = "Dr. Sunil Rajendran"

            result = {
                'status': status,
                'medicine': medicine if (status == "normal") else "Requires Doctor Consultation",
                'advice': answer if answer else "Please consult Dr. Sunil Rajendran.",
                'doctor_name': final_doc_name,
                'name': patient_name
            }

    return render(request, 'hospital/index.html', {
        'result': result, 
        'today_date': today_str
    })

# def home_view(request):
#     if request.user.is_authenticated:    #original 2
#         return HttpResponseRedirect('afterlogin')

#     result = None
#     # Always provide today_date so forms never have empty date fields
#     today_str = datetime.date.today().strftime('%Y-%m-%d')
    
#     if request.method == 'POST' and 'symptom1' in request.POST:
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}".strip()
#         request.session['temp_symptoms'] = user_query 

#         try:
#             query_vector = embed_model.encode(user_query).tolist()
#         except Exception as e:
#             print(f"Embedding Error: {e}")
#             query_vector = None

#         db_row = None
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         try:
#             if query_vector:
#                 search_query = "SELECT question, answer, medicine FROM medical_knowledge ORDER BY embedding <=> %s::vector LIMIT 1;"
#                 cur.execute(search_query, (query_vector,))
#                 db_row = cur.fetchone()
#             else:
#                 cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#                 db_row = cur.fetchone()
#         except Exception as e:
#             conn.rollback() 
#             cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#             db_row = cur.fetchone()
#         finally:
#             cur.close()
#             conn.close()

#         if db_row:
#             matched_q, answer, medicine = db_row
#             matched_q = matched_q.lower()
#             user_query_low = user_query.lower()
            
#             # Dept logic
#             if any(word in matched_q for word in ['stomach', 'acidity', 'gastric']):
#                 dept_to_find = "Colon and Rectal Surgeons"
#             elif any(word in matched_q for word in ['skin', 'rash', 'dermatology']):
#                 dept_to_find = "Dermatologists"
#             elif any(word in matched_q for word in ['accident', 'emergency', 'broken']):
#                 dept_to_find = "Emergency Medicine Specialists"
#             else:
#                 dept_to_find = "General"

#             suggested_doctor = models.Doctor.objects.filter(department__icontains=dept_to_find, status=True).first()

#             # 5. STATUS & MEDICINE LOGIC
#             chronic_keywords = ['week', 'month', 'years', 'long time', 'persistent', 'since']

#             if any(word in user_query_low for word in ['broken', 'bleed', 'emergency', 'accident', 'chest pain']):
#                 status = "emergency"
#             elif any(word in user_query_low for word in chronic_keywords):
#                 status = "consultation"
#             elif medicine and medicine.lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             # ENSURE doctor_name IS NEVER EMPTY (This prevents the widget from crashing)
#             if not suggested_doctor:
#                 # Default to Dr. vikas gupta if no specialist is found for back pain
#                 final_doc_name = "Dr. vikas gupta (General)"
#             else:
#                 final_doc_name = f"Dr. {suggested_doctor.user.first_name} ({suggested_doctor.department})"

#             result = {
#                 'status': status,
#                 'medicine': medicine if (status == "normal") else "Requires Doctor Consultation",
#                 'advice': answer if answer else "Please consult a specialist for your persistent symptoms.",
#                 'doctor_name': final_doc_name,
#                 'name': patient_name
#             }

#     # CRITICAL FIX: The context MUST contain 'result' even if it's None 
#     # and 'today_date' must be present for the hidden fields.
#     return render(request, 'hospital/index.html', {
#         'result': result, 
#         'today_date': today_str
#     })


# Create your views here.
# def home_view(request): #original 1
#     # 1. First, check if user is already logged in
#     if request.user.is_authenticated:
#         return HttpResponseRedirect('afterlogin')

#     result = None
    
#     # 2. CHATBOT LOGIC: Catch the form data from the widget
#     if request.method == 'POST' and 'symptom1' in request.POST:
#         # Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # Get Input and Create Embedding
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}".strip()
#         request.session['temp_symptoms'] = user_query 

#         try:
#             # Ensure embed_model is initialized globally in views.py
#             query_vector = embed_model.encode(user_query).tolist()
#         except Exception as e:
#             print(f"Embedding Error: {e}")
#             query_vector = None

#         # 3. SEMANTIC SEARCH LOGIC
#         db_row = None
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         try:
#             if query_vector:
#                 search_query = """
#                     SELECT question, answer, medicine 
#                     FROM medical_knowledge 
#                     ORDER BY embedding <=> %s::vector 
#                     LIMIT 1;
#                 """
#                 cur.execute(search_query, (query_vector,))
#                 db_row = cur.fetchone()
#             else:
#                 cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#                 db_row = cur.fetchone()
#         except Exception as e:
#             print(f"Database Error: {e}")
#             conn.rollback() 
#             cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#             db_row = cur.fetchone()
#         finally:
#             cur.close()
#             conn.close()

#         if db_row:
#             matched_q, answer, medicine = db_row
#             matched_q = matched_q.lower()
#             user_query_low = user_query.lower()
            
#             # 4. DYNAMIC DOCTOR LOGIC
#             if any(word in matched_q for word in ['stomach', 'acidity', 'rectal', 'gastric', 'digestion']):
#                 dept_to_find = "Colon and Rectal Surgeons"
#             elif any(word in matched_q for word in ['skin', 'rash', 'acne', 'dermatology']):
#                 dept_to_find = "Dermatologists"
#             elif any(word in matched_q for word in ['pain', 'back', 'neck', 'spine']):
#                 dept_to_find = "General"
#             elif any(word in matched_q for word in ['accident', 'emergency', 'broken', 'fracture']):
#                 dept_to_find = "Emergency Medicine Specialists"
#             else:
#                 dept_to_find = "General"

#             suggested_doctor = models.Doctor.objects.filter(
#                 department__icontains=dept_to_find,
#                 status=True
#             ).first()

#             # 5. STATUS & MEDICINE LOGIC
#             chronic_keywords = ['week', 'month', 'years', 'long time', 'persistent', 'since']

#             if any(word in user_query_low for word in ['broken', 'bleed', 'emergency', 'accident', 'chest pain']):
#                 status = "emergency"
#             elif any(word in user_query_low for word in chronic_keywords):
#                 status = "consultation"
#             elif medicine and medicine.lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if (status == "normal") else "Requires Doctor Consultation",
#                 'advice': answer,
#                 'doctor_name': f"Dr. {suggested_doctor.user.first_name} ({suggested_doctor.department})" if suggested_doctor else "Dr. Sunil Rajendran (MBBS)",
#                 'name': patient_name
#             }
#         else:
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found. Please consult our staff.',
#                 'doctor_name': 'Dr. Sunil Rajendran MBBS'
#             }

#     # 6. Final Render (Crucial: Passes result back to index.html)
#     return render(request, 'hospital/index.html', {'result': result})

#for showing signup/login button for admin(by sumit)
def adminclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'hospital/adminclick.html')


#for showing signup/login button for doctor(by sumit)
def doctorclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'hospital/doctorclick.html')


#for showing signup/login button for patient(by sumit)
def patientclick_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('afterlogin')
    return render(request,'hospital/patientclick.html')




def admin_signup_view(request):
    form=forms.AdminSigupForm()
    if request.method=='POST':
        form=forms.AdminSigupForm(request.POST)
        if form.is_valid():
            user=form.save()
            user.set_password(user.password)
            user.save()
            my_admin_group = Group.objects.get_or_create(name='ADMIN')
            my_admin_group[0].user_set.add(user)
            return HttpResponseRedirect('adminlogin')
    return render(request,'hospital/adminsignup.html',{'form':form})




# def doctor_signup_view(request):
#     userForm=forms.DoctorUserForm()
#     doctorForm=forms.DoctorForm()
#     mydict={'userForm':userForm,'doctorForm':doctorForm}
#     if request.method=='POST':
#         userForm=forms.DoctorUserForm(request.POST)
#         doctorForm=forms.DoctorForm(request.POST,request.FILES)
#         if userForm.is_valid() and doctorForm.is_valid():
#             user=userForm.save()
#             user.set_password(user.password)
#             user.save()

#             doctor=doctorForm.save(commit=False)
#             doctor.user=user
#             # doctor.status=False
#             doctor=doctor.save()
#             models.Doctor.objects.filter(id=doctor.id).update(status=False)

#             my_doctor_group = Group.objects.get_or_create(name='DOCTOR')
#             my_doctor_group[0].user_set.add(user)
#         return HttpResponseRedirect('doctorlogin')
#     return render(request,'hospital/doctorsignup.html',{'userForm':userForm,'doctorForm':doctorForm})

def doctor_signup_view(request):
    userForm = forms.DoctorUserForm()
    doctorForm = forms.DoctorForm()
    if request.method == 'POST':
        userForm = forms.DoctorUserForm(request.POST)
        doctorForm = forms.DoctorForm(request.POST, request.FILES)
        if userForm.is_valid() and doctorForm.is_valid():
            user = userForm.save()
            user.set_password(user.password)
            user.save()
            
            doctor = doctorForm.save(commit=False)
            doctor.user = user
            doctor.save() # This might save as True due to hidden bugs
            
            # --- THE FINAL FIX ---
            # This line forces the database to change it to False 
            # It ignores every other setting in your project.
            models.Doctor.objects.filter(id=doctor.id).update(status=False)
            
            # Add to Group
            from django.contrib.auth.models import Group
            group = Group.objects.get_or_create(name='DOCTOR')
            group[0].user_set.add(user)
            
            return HttpResponseRedirect('doctorlogin')
    return render(request, 'hospital/doctorsignup.html', {'userForm': userForm, 'doctorForm': doctorForm})


# def patient_signup_view(request):
#     userForm=forms.PatientUserForm()
#     patientForm=forms.PatientForm()
#     mydict={'userForm':userForm,'patientForm':patientForm}

#     if request.method=='POST':
#         userForm=forms.PatientUserForm(request.POST)
#         patientForm=forms.PatientForm(request.POST,request.FILES)

#         if userForm.is_valid() and patientForm.is_valid():
#             user=userForm.save()
#             user.set_password(user.password)
#             user.save()

#             # my_patient_group = Group.objects.get_or_create(name='PATIENT')
#             # my_patient_group[0].user_set.add(user)

#             group, created = Group.objects.get_or_create(name='PATIENT')

#             user.groups.add(group)
#             user.save()

#             patient=patientForm.save(commit=False)
#             patient.user=user

#             patient.assignedDoctorId=request.POST.get('assignedDoctorId')
#             patient.save()

#             patient = models.Patient.objects.get(user=user)

#             models.Appointment.objects.create(
#                 patientId=patient.id,
#                 patientName=patient.get_name,
#                 doctorId=patient.assignedDoctorId,
#                 doctorName=patient.doctorName,
#                 department=patient.department,
#                 appointmentDate=patient.admitDate, 
#                 description=patient.symptoms,
#                 status=False
#             )

    
           
#         return HttpResponseRedirect('patientlogin')
    
#     return render(request,'hospital/patientsignup.html',context=mydict)

def patient_signup_view(request):
    userForm = forms.PatientUserForm()
    patientForm = forms.PatientForm()
    mydict = {'userForm': userForm, 'patientForm': patientForm}
    
    if request.method == 'POST':
        userForm = forms.PatientUserForm(request.POST)
        patientForm = forms.PatientForm(request.POST, request.FILES)
        
        
        if userForm.is_valid() and patientForm.is_valid():
            # 1. Save User
            user = userForm.save()
            user.set_password(user.password)
            user.save()
            
            # 2. Save Patient Profile
            patient = patientForm.save(commit=False)
            patient.user = user
            
            patient.assignedDoctorId = request.POST.get('assignedDoctorId')
            patient.save()
            
            # 3. Add to Group
            my_patient_group = Group.objects.get_or_create(name='PATIENT')
            my_patient_group[0].user_set.add(user)

            chosen_date = request.POST.get('appointment_date')
            print(f"--- ATTEMPTING TO SAVE DATE: {chosen_date} ---")
            doc_id = request.POST.get('assignedDoctorId')
            symptoms = request.POST.get('symptoms') # Ensure this name matches your HTML input
            
            try:
                doctor = models.Doctor.objects.get(id=doc_id)
                models.Appointment.objects.create(
                    patientId=user.id,
                    patientName=user.first_name,
                    doctorId=doc_id,
                    doctorName=doctor.get_name, 
                    appointmentDate=chosen_date,
                    description=symptoms,
                    status=False
                )
            except Exception as e:
                print(f"Appointment Auto-Creation Failed: {e}")

            return redirect('patientlogin')
        else:
            
            mydict = {'userForm': userForm, 'patientForm': patientForm}

    return render(request, 'hospital/patientsignup.html', context=mydict)






#-----------for checking user is doctor , patient or admin(by sumit)
def is_admin(user):
    return user.groups.filter(name='ADMIN').exists() or user.is_superuser
def is_doctor(user):
    return user.groups.filter(name='DOCTOR').exists()
def is_patient(user):
    # return user.groups.filter(name='PATIENT').exists()
    return user.groups.filter(name__iexact='PATIENT').exists()


#---------AFTER ENTERING CREDENTIALS WE CHECK WHETHER USERNAME AND PASSWORD IS OF ADMIN,DOCTOR OR PATIENT
def afterlogin_view(request):
    print(f"USER: {request.user.username} | GROUPS: {request.user.groups.all()}")

    if is_admin(request.user):
        return redirect('admin-dashboard')
    elif is_doctor(request.user):
        accountapproval=models.Doctor.objects.all().filter(user_id=request.user.id,status=True)
        if accountapproval:
            return redirect('doctor-dashboard')
        else:
            return render(request,'hospital/doctor_wait_for_approval.html')
    elif is_patient(request.user):
        accountapproval=models.Patient.objects.all().filter(user_id=request.user.id,status=True)
        if accountapproval:
            return redirect('patient-dashboard')
        else:
            return render(request,'hospital/patient_wait_for_approval.html')

    else:
        # FALLBACK: If the user is a superuser but isn't in the 'ADMIN' group,
        # or if it's a generic user, send them to the admin dashboard.
        from django.contrib.auth import logout
        logout(request)
        return redirect('/')
        # return redirect('admin-dashboard')






#---------------------------------------------------------------------------------
#------------------------ ADMIN RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    #for both table in admin dashboard
    doctors=models.Doctor.objects.all().order_by('-id')
    patients=models.Patient.objects.all().order_by('-id')
    #for three cards
    doctorcount=models.Doctor.objects.all().filter(status=True).count()
    pendingdoctorcount=models.Doctor.objects.all().filter(status=False).count()

    patientcount=models.Patient.objects.all().filter(status=True).count()
    pendingpatientcount=models.Patient.objects.all().filter(status=False).count()

    appointmentcount=models.Appointment.objects.all().filter(status=True).count()
    pendingappointmentcount=models.Appointment.objects.all().filter(status=False).count()
    mydict={
    'doctors':doctors,
    'patients':patients,
    'doctorcount':doctorcount,
    'pendingdoctorcount':pendingdoctorcount,
    'patientcount':patientcount,
    'pendingpatientcount':pendingpatientcount,
    'appointmentcount':appointmentcount,
    'pendingappointmentcount':pendingappointmentcount,
    }
    return render(request,'hospital/admin_dashboard.html',context=mydict)


# this view for sidebar click on admin page
@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_doctor_view(request):
    return render(request,'hospital/admin_doctor.html')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_view_doctor_view(request):
    doctors=models.Doctor.objects.all().filter(status=True)
    return render(request,'hospital/admin_view_doctor.html',{'doctors':doctors})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def delete_doctor_from_hospital_view(request,pk):
    doctor=models.Doctor.objects.get(id=pk)
    user=models.User.objects.get(id=doctor.user_id)
    user.delete()
    doctor.delete()
    return redirect('admin-view-doctor')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def update_doctor_view(request,pk):
    doctor=models.Doctor.objects.get(id=pk)
    user=models.User.objects.get(id=doctor.user_id)

    userForm=forms.DoctorUserForm(instance=user)
    doctorForm=forms.DoctorForm(request.FILES,instance=doctor)
    mydict={'userForm':userForm,'doctorForm':doctorForm}
    if request.method=='POST':
        userForm=forms.DoctorUserForm(request.POST,instance=user)
        doctorForm=forms.DoctorForm(request.POST,request.FILES,instance=doctor)
        if userForm.is_valid() and doctorForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            doctor=doctorForm.save(commit=False)
            doctor.status=True
            doctor.save()
            return redirect('admin-view-doctor')
    return render(request,'hospital/admin_update_doctor.html',context=mydict)




@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_add_doctor_view(request):
    userForm=forms.DoctorUserForm()
    doctorForm=forms.DoctorForm()
    mydict={'userForm':userForm,'doctorForm':doctorForm}
    if request.method=='POST':
        userForm=forms.DoctorUserForm(request.POST)
        doctorForm=forms.DoctorForm(request.POST, request.FILES)
        if userForm.is_valid() and doctorForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()

            doctor=doctorForm.save(commit=False)
            doctor.user=user
            doctor.status=True
            doctor.save()

            my_doctor_group = Group.objects.get_or_create(name='DOCTOR')
            my_doctor_group[0].user_set.add(user)

        return HttpResponseRedirect('admin-view-doctor')
    return render(request,'hospital/admin_add_doctor.html',context=mydict)




@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_approve_doctor_view(request):
    #those whose approval are needed
    doctors=models.Doctor.objects.all().filter(status=False)
    return render(request,'hospital/admin_approve_doctor.html',{'doctors':doctors})


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def approve_doctor_view(request, pk): 
    doctor=models.Doctor.objects.get(id = pk)
    doctor.status=True
    doctor.save()
    return redirect('admin-approve-doctor')
    # return redirect(reverse('admin-approve-doctor'))


@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def reject_doctor_view(request,pk):
    doctor=models.Doctor.objects.get(id=pk)
    user=models.User.objects.get(id=doctor.user_id)
    user.delete()
    doctor.delete()
    return redirect('admin-approve-doctor')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_view_doctor_specialisation_view(request):
    doctors=models.Doctor.objects.all().filter(status=True)
    return render(request,'hospital/admin_view_doctor_specialisation.html',{'doctors':doctors})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_patient_view(request):
    return render(request,'hospital/admin_patient.html')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_view_patient_view(request):
    patients=models.Patient.objects.all().filter(status=True)
    return render(request,'hospital/admin_view_patient.html',{'patients':patients})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def delete_patient_from_hospital_view(request,pk):
    patient=models.Patient.objects.get(id=pk)
    user=models.User.objects.get(id=patient.user_id)
    user.delete()
    patient.delete()
    return redirect('admin-view-patient')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def update_patient_view(request,pk):
    patient=models.Patient.objects.get(id=pk)
    user=models.User.objects.get(id=patient.user_id)

    userForm=forms.PatientUserForm(instance=user)
    patientForm=forms.PatientForm(request.FILES,instance=patient)
    mydict={'userForm':userForm,'patientForm':patientForm}
    if request.method=='POST':
        userForm=forms.PatientUserForm(request.POST,instance=user)
        patientForm=forms.PatientForm(request.POST,request.FILES,instance=patient)
        if userForm.is_valid() and patientForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()
            patient=patientForm.save(commit=False)
            patient.status=True
            patient.assignedDoctorId=request.POST.get('assignedDoctorId')
            patient.save()
            return redirect('admin-view-patient')
    return render(request,'hospital/admin_update_patient.html',context=mydict)





@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_add_patient_view(request):
    userForm=forms.PatientUserForm()
    patientForm=forms.PatientForm()
    mydict={'userForm':userForm,'patientForm':patientForm}
    if request.method=='POST':
        userForm=forms.PatientUserForm(request.POST)
        patientForm=forms.PatientForm(request.POST,request.FILES)
        if userForm.is_valid() and patientForm.is_valid():
            user=userForm.save()
            user.set_password(user.password)
            user.save()

            patient=patientForm.save(commit=False)
            patient.user=user
            patient.status=True
            patient.assignedDoctorId=request.POST.get('assignedDoctorId')
            patient.save()

            my_patient_group = Group.objects.get_or_create(name='PATIENT')
            my_patient_group[0].user_set.add(user)

        return HttpResponseRedirect('admin-view-patient')
    return render(request,'hospital/admin_add_patient.html',context=mydict)



#------------------FOR APPROVING PATIENT BY ADMIN----------------------
@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_approve_patient_view(request):
    #those whose approval are needed
    patients=models.Patient.objects.all().filter(status=False)
    return render(request,'hospital/admin_approve_patient.html',{'patients':patients})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def approve_patient_view(request,pk):
    patient=models.Patient.objects.get(id=pk)
    user = models.User.objects.get(id=patient.user_id)
    patient.status=True
    patient.save()

    models.Appointment.objects.filter(
        patientId=user.id,
        patientName=user.first_name,
        doctorId=patient.assignedDoctorId,
        # Fetch doctor name from the Doctor model
        doctorName=models.Doctor.objects.get(id=patient.assignedDoctorId).get_name,
        # appointmentDate=timezone.now().date(),
        description=patient.symptoms,
        status=False 
    ).update(status=True)

    return redirect(reverse('admin-approve-patient'))



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def reject_patient_view(request,pk):
    patient=models.Patient.objects.get(id=pk)
    user=models.User.objects.get(id=patient.user_id)
    user.delete()
    patient.delete()
    return redirect('admin-approve-patient')



#--------------------- FOR DISCHARGING PATIENT BY ADMIN START-------------------------
@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_discharge_patient_view(request):
    patients=models.Patient.objects.all().filter(status=True)
    return render(request,'hospital/admin_discharge_patient.html',{'patients':patients})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def discharge_patient_view(request,pk):
    patient=models.Patient.objects.get(id=pk)
    days=(date.today()-patient.admitDate) #2 days, 0:00:00
    assignedDoctor=models.User.objects.all().filter(id=patient.assignedDoctorId)
    d=days.days # only how many day that is 2
    patientDict={
        'patientId':pk,
        'name':patient.get_name,
        'mobile':patient.mobile,
        'address':patient.address,
        'symptoms':patient.symptoms,
        'admitDate':patient.admitDate,
        'todayDate':date.today(),
        'day':d,
        'assignedDoctorName':assignedDoctor[0].first_name,
    }
    if request.method == 'POST':
        feeDict ={
            'roomCharge':int(request.POST['roomCharge'])*int(d),
            'doctorFee':request.POST['doctorFee'],
            'medicineCost' : request.POST['medicineCost'],
            'OtherCharge' : request.POST['OtherCharge'],
            'total':(int(request.POST['roomCharge'])*int(d))+int(request.POST['doctorFee'])+int(request.POST['medicineCost'])+int(request.POST['OtherCharge'])
        }
        patientDict.update(feeDict)
        #for updating to database patientDischargeDetails (pDD)
        pDD=models.PatientDischargeDetails()
        pDD.patientId=pk
        pDD.patientName=patient.get_name
        pDD.assignedDoctorName=assignedDoctor[0].first_name
        pDD.address=patient.address
        pDD.mobile=patient.mobile
        pDD.symptoms=patient.symptoms
        pDD.admitDate=patient.admitDate
        pDD.releaseDate=date.today()
        pDD.daySpent=int(d)
        pDD.medicineCost=int(request.POST['medicineCost'])
        pDD.roomCharge=int(request.POST['roomCharge'])*int(d)
        pDD.doctorFee=int(request.POST['doctorFee'])
        pDD.OtherCharge=int(request.POST['OtherCharge'])
        pDD.total=(int(request.POST['roomCharge'])*int(d))+int(request.POST['doctorFee'])+int(request.POST['medicineCost'])+int(request.POST['OtherCharge'])
        pDD.save()
        return render(request,'hospital/patient_final_bill.html',context=patientDict)
    return render(request,'hospital/patient_generate_bill.html',context=patientDict)



#--------------for discharge patient bill (pdf) download and printing



def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return HttpResponse("Error generating PDF", status=400)



# def download_pdf_view(request,pk):
#     dischargeDetails=models.PatientDischargeDetails.objects.all().filter(patientId=pk).order_by('-id')[:1]
#     dict={
#         'patientName':dischargeDetails[0].patientName,
#         'assignedDoctorName':dischargeDetails[0].assignedDoctorName,
#         'address':dischargeDetails[0].address,
#         'mobile':dischargeDetails[0].mobile,
#         'symptoms':dischargeDetails[0].symptoms,
#         'admitDate':dischargeDetails[0].admitDate,
#         'releaseDate':dischargeDetails[0].releaseDate,
#         'daySpent':dischargeDetails[0].daySpent,
#         'medicineCost':dischargeDetails[0].medicineCost,
#         'roomCharge':dischargeDetails[0].roomCharge,
#         'doctorFee':dischargeDetails[0].doctorFee,
#         'OtherCharge':dischargeDetails[0].OtherCharge,
#         'total':dischargeDetails[0].total,
#     }
#     return render_to_pdf('hospital/download_bill.html',dict)

def download_pdf_view(request, pk):
    # 1. Get the queryset
    discharge_queryset = models.PatientDischargeDetails.objects.filter(patientId=pk).order_by('-id')
    
    # 2. Check if the record actually exists
    if not discharge_queryset.exists():
        return HttpResponse(f"No discharge records found for Patient ID {pk}. Please ensure the patient is discharged before downloading the bill.")

    # 3. Get the single record safely
    obj = discharge_queryset[0]
    
    # 4. Build the dictionary
    context = {
        'patientName': obj.patientName,
        'assignedDoctorName': obj.assignedDoctorName,
        'address': obj.address,
        'mobile': obj.mobile,
        'symptoms': obj.symptoms,
        'admitDate': obj.admitDate,
        'releaseDate': obj.releaseDate,
        'daySpent': obj.daySpent,
        'medicineCost': obj.medicineCost,
        'roomCharge': obj.roomCharge,
        'doctorFee': obj.doctorFee,
        'OtherCharge': obj.OtherCharge,
        'total': obj.total,
    }
    
    return render_to_pdf('hospital/download_bill.html', context)



#-----------------APPOINTMENT START--------------------------------------------------------------------
@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_appointment_view(request):
    return render(request,'hospital/admin_appointment.html')



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_view_appointment_view(request):
    appointments=models.Appointment.objects.all().filter(status=True)
    return render(request,'hospital/admin_view_appointment.html',{'appointments':appointments})



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_add_appointment_view(request):
    appointmentForm=forms.AppointmentForm()
    mydict={'appointmentForm':appointmentForm,}
    if request.method=='POST':
        appointmentForm=forms.AppointmentForm(request.POST)
        if appointmentForm.is_valid():
            appointment=appointmentForm.save(commit=False)
            appointment.doctorId=request.POST.get('doctorId')
            appointment.patientId=request.POST.get('patientId')
            appointment.doctorName=models.User.objects.get(id=request.POST.get('doctorId')).first_name
            appointment.patientName=models.User.objects.get(id=request.POST.get('patientId')).first_name
            appointment.status=True
            appointment.save()
        return HttpResponseRedirect('admin-view-appointment')
    return render(request,'hospital/admin_add_appointment.html',context=mydict)

@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def admin_approve_appointment_view(request):
    # Those whose approval are needed
    appointments = models.Appointment.objects.all().filter(status=False)
    return render(request, 'hospital/admin_approve_appointment.html', {'appointments': appointments})

from django.contrib.auth.models import User, Group
from . import models

# Change the decorator to allow both Doctors and Admins
@login_required(login_url='doctorlogin')
def approve_appointment_view(request, pk):
    # 1. Get the appointment
    appointment = models.Appointment.objects.get(id=pk)
    
    # 2. Get the Doctor (We need the .id, not the user_id)
    doctor = models.Doctor.objects.get(user_id=request.user.id)

    # 3. Create a unique User for this patient
    username = f"patient_{appointment.id}"
    user, created = User.objects.get_or_create(username=username)
    if created:
        user.first_name = appointment.patientName
        user.save()
        # Ensure they belong to the PATIENT group
        from django.contrib.auth.models import Group
        group, _ = Group.objects.get_or_create(name='PATIENT')
        user.groups.add(group)

    # 4. Create the Patient Record (Filling all required fields)
    patient, p_created = models.Patient.objects.update_or_create(
        user=user,
        defaults={
            'address': "AI Triage Guest",
            'mobile': appointment.mobile,
            'symptoms': appointment.description[:100],
            'status': True,  # MUST be True to show in Patient List
            'assignedDoctorId': doctor.id  # Matches doctor's primary key
        }
    )

    # 5. Finalize the Appointment
    appointment.status = True
    appointment.patientId = patient.id # Links Appointment to Patient PK
    appointment.save()

    return redirect('doctor-dashboard')

# @login_required(login_url='adminlogin')
# @user_passes_test(is_admin)
# def admin_approve_appointment_view(request):
#     #those whose approval are needed
#     appointments=models.Appointment.objects.all().filter(status=False)
#     return render(request,'hospital/admin_approve_appointment.html',{'appointments':appointments})



# @login_required(login_url='adminlogin')
# @user_passes_test(is_admin)
# def approve_appointment_view(request, pk):
#     appointment=models.Appointment.objects.get(id =pk)
#     appointment.status=True
#     appointment.save()
#     return redirect(reverse('admin-approve-appointment'))



@login_required(login_url='adminlogin')
@user_passes_test(is_admin)
def reject_appointment_view(request,pk):
    appointment=models.Appointment.objects.get(id=pk)
    appointment.delete()
    return redirect('admin-approve-appointment')
#---------------------------------------------------------------------------------
#------------------------ ADMIN RELATED VIEWS END ------------------------------
#---------------------------------------------------------------------------------






#---------------------------------------------------------------------------------
#------------------------ DOCTOR RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_dashboard_view(request):
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
#     if doctor.status:
#         return render(request, 'hospital/doctor_dashboard.html', {'doctor': doctor})
#     else:
#         return render(request, 'hospital/doctor_wait_fro_approval.html')

#     # try:
#     #     doctor = models.Doctor.objects.get(user_id=request.user.id)
#     # except models.Doctor.DoesNotExist:
#     #     # Fallback if the doctor record is missing
#     #     return HttpResponse("Doctor profile not found. Please contact Admin.")

#     #for three cards
#     patientcount=models.Patient.objects.all().filter(status=True,assignedDoctorId=request.user.id).count()
#     appointmentcount=models.Appointment.objects.all().filter(status=True,doctorId=request.user.id).count()
#     patientdischarged=models.PatientDischargeDetails.objects.all().distinct().filter(assignedDoctorName=request.user.first_name).count()

#     #for  table in doctor dashboard
#     appointments=models.Appointment.objects.all().filter(status=True,doctorId=request.user.id).order_by('-id')
#     patientid=[]
#     for a in appointments:
#         patientid.append(a.patientId)
#     patients=models.Patient.objects.all().filter(status=True,user_id__in=patientid).order_by('-id')
#     appointments=zip(appointments,patients)
    
#     mydict={
#     'doctor':doctor,     #models.Doctor.objects.get(user_id=request.user.id), #for profile picture of doctor in sidebar
#     'patientcount':patientcount,
#     'appointmentcount':appointmentcount,
#     'patientdischarged':patientdischarged,
#     'appointments':appointments,
    
#     }
#     return render(request,'hospital/doctor_dashboard.html',context=mydict)

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_dashboard_view(request):
#     # 1. Fetch the doctor profile
#     try:
#         doctor = models.Doctor.objects.get(user_id=request.user.id)
#     except models.Doctor.DoesNotExist:
#         return HttpResponse("Doctor profile not found. Please contact Admin.")

#     # 2. Check Approval Status immediately
#     # If not approved, send to wait page and STOP here.
#     if not doctor.status:
#         return render(request, 'hospital/doctor_wait_for_approval.html', {'doctor': doctor})

#     # 3. If we reach here, the doctor IS approved. Calculate counts:
#     # Use doctor.id for filtering as we discussed earlier to avoid mismatches
#     patientcount = models.Patient.objects.filter(status=True, assignedDoctorId=doctor.id).count()
#     appointmentcount = models.Appointment.objects.filter(status=True, doctorId=doctor.id).count()
#     patientdischarged = models.PatientDischargeDetails.objects.filter(assignedDoctorName=request.user.first_name).distinct().count()

#     # 4. Fetch table data
#     appointments_queryset = models.Appointment.objects.filter(status=True, doctorId=doctor.id).order_by('-id')
    
#     patientid = []
#     for a in appointments_queryset:
#         patientid.append(a.patientId)
    
#     # We check both ID and User_ID to be safe as per our previous fix
#     patients = models.Patient.objects.filter(status=True, id__in=patientid).order_by('-id')
    
#     # Zip them together for the table
#     appointments_zipped = zip(appointments_queryset, patients)

#     # 5. Build context and return the dashboard
#     mydict = {
#         'doctor': doctor,
#         'patientcount': patientcount,
#         'appointmentcount': appointmentcount,
#         'patientdischarged': patientdischarged,
#         'appointments': appointments_zipped,
#     }
#     return render(request, 'hospital/doctor_dashboard.html', context=mydict)

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_dashboard_view(request):
#     # STEP 1: Define the variable 'doctor' clearly
#     # We use .filter().first() to avoid a crash if the doctor record is missing
#     # doctor = models.Doctor.objects.filter(user_id=request.user.id)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)

#     # patients = models.Patient.objects.filter(assignedDoctorId=doctor.id)

#     # STEP 2: Logic for the cards
#     patientcount = models.Patient.objects.all().filter(status=True, assignedDoctorId=request.user.id).count()
#     appointmentcount = models.Appointment.objects.all().filter(status=True, doctorId=request.user.id).count()
#     # appointmentcount = appointments.count()
#     patientdischarged = models.PatientDischargeDetails.objects.all().distinct().filter(assignedDoctorName=request.user.first_name).count()

#     # STEP 3: Logic for the appointments table
#     appointments = models.Appointment.objects.all().filter(status=True, doctorId=request.user.id).order_by('-id')   
#     patientid = []
#     for a in appointments:
#         patientid.append(a.patientId)

#     patients = models.Patient.objects.all().filter(status=True, user_id__in=patientid).order_by('-id')
#     appointments_zipped = zip(appointments, patients)

#     # STEP 4: The Dictionary (Ensure 'doctor' matches the variable in Step 1)
#     mydict = {
#         'patientcount': patientcount,
#         'appointmentcount': appointmentcount,
#         'patientdischarged': patientdischarged,
#         'appointments': appointments_zipped,
#         'doctor': doctor,  
#     }
    
#     return render(request, 'hospital/doctor_dashboard.html', context=mydict)

from django.db.models import Q

@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_dashboard_view(request):
    # STEP 1: Get the doctor object
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    
    # Use the doctor's first name (e.g., Sunil) for a broad search
    search_term = doctor.user.first_name.strip()

    # STEP 2: Logic for the cards
    
    # 1. GET APPOINTMENT DATA FIRST
    appointments = models.Appointment.objects.filter(
        status=True, 
        doctorName__icontains=search_term
    ).order_by('-id')
    
    # Get IDs of patients from those appointments (Your 7 Old Patients)
    appointment_patient_ids = appointments.values_list('patientId', flat=True)

    # 2. FIX THE PATIENT COUNT (The "11" Fix)
    # This counts patients assigned by ID (AI) OR found in appointments (Old)
    patientcount = models.Patient.objects.filter(
        Q(assignedDoctorId=doctor.id) | Q(id__in=appointment_patient_ids),
        status=True
    ).distinct().count()
    
    appointmentcount = appointments.count()
    
    # Logic for discharged patients
    patientdischarged = models.PatientDischargeDetails.objects.all().distinct().filter(
        assignedDoctorName__icontains=search_term
    ).count()

    # STEP 3: Logic for the appointments table
    patients_list = []
    for a in appointments:
        p = models.Patient.objects.filter(id=a.patientId, status=True).first()
        patients_list.append(p)

    appointments_zipped = zip(appointments, patients_list)

    # STEP 4: The Context Dictionary
    mydict = {
        'patientcount': patientcount, # Now this will show 11
        'appointmentcount': appointmentcount,
        'patientdischarged': patientdischarged,
        'appointments': appointments_zipped,
        'doctor': doctor,  
    }
    
    return render(request, 'hospital/doctor_dashboard.html', context=mydict)

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# @login_required
# def doctor_dashboard_view(request):
#     # STEP 1: Get the doctor object
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # IMPROVEMENT: Strip '@' and use username or name for a broader search
#     # This ensures @janu finds appointments for "Janu" or "@janu"
#     search_term = doctor.user.username.replace('@', '').strip()

#     # STEP 2: Logic for the cards
#     # Patients explicitly assigned to this doctor's ID
#     patientcount = models.Patient.objects.all().filter(status=True, assignedDoctorId=request.user.id).count()
    
#     # Filter appointments by the doctor's name (covers AI chatbot bookings)
#     appointments = models.Appointment.objects.filter(
#         status=True, 
#         doctorName__icontains=search_term
#     ).order_by('-id')
    
#     appointmentcount = appointments.count()
    
#     # Logic for discharged patients
#     patientdischarged = models.PatientDischargeDetails.objects.all().distinct().filter(
#         assignedDoctorName__icontains=search_term
#     ).count()

#     # STEP 3: Logic for the appointments table (Handling AI Walk-ins)
#     patients_list = []
#     for a in appointments:
#         # If the appointment has a patientId, find the record. 
#         # If it's a chatbot walk-in, this will safely return None.
#         p = models.Patient.objects.filter(id=a.patientId, status=True).first()
#         # p = models.Patient.objects.filter(status=True, user_id=a.patientId).first()
#         patients_list.append(p)

#     # Zip appointments with patient records (or None for AI users)
#     appointments_zipped = zip(appointments, patients_list)

#     # STEP 4: The Context Dictionary
#     mydict = {
#         'patientcount': patientcount,
#         'appointmentcount': appointmentcount,
#         'patientdischarged': patientdischarged,
#         'appointments': appointments_zipped,
#         'doctor': doctor,  
#     }
    
#     return render(request, 'hospital/doctor_dashboard.html', context=mydict)

# def doctor_dashboard_view(request):
#     # STEP 1: Get the doctor object
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
#     search_term = doctor.get_name.strip()

#     # STEP 2: Logic for the cards
#     # Filter by doctorId for registered patients, or doctorName for AI/Walk-ins
#     patientcount = models.Patient.objects.all().filter(status=True, assignedDoctorId=request.user.id).count()
    
#     # Update appointment count to include AI bookings
#     appointments = models.Appointment.objects.filter(
#         status=True, 
#         doctorName__icontains=search_term
#     ).order_by('-id')
    
#     appointmentcount = appointments.count()
    
#     patientdischarged = models.PatientDischargeDetails.objects.all().distinct().filter(
#         assignedDoctorName=request.user.first_name
#     ).count()

#     # STEP 3: Logic for the appointments table (The "Zipped" Logic)
#     # Since AI patients don't have a Patient Model record, we must handle 'None' patients
#     patients_list = []
#     for a in appointments:
#         # Try to find a registered patient record
#         p = models.Patient.objects.filter(status=True, user_id=a.patientId).first()
#         # If no registered patient exists (AI Walk-in), we append None
#         patients_list.append(p)

#     # Zip the AI-friendly appointments with the patients (even if patient is None)
#     appointments_zipped = zip(appointments, patients_list)

#     # STEP 4: The Dictionary
#     mydict = {
#         'patientcount': patientcount,
#         'appointmentcount': appointmentcount,
#         'patientdischarged': patientdischarged,
#         'appointments': appointments_zipped,
#         'doctor': doctor,  
#     }
    
#     return render(request, 'hospital/doctor_dashboard.html', context=mydict)

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_dashboard_view(request):
#     # STEP 1: Get the Doctor profile (we need doctor.id, not request.user.id)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)

#     # STEP 2: Logic for the cards (Use doctor.id for filtering)
#     # We remove status=True for the count to show ALL appointments (pending + approved)
#     patientcount = models.Patient.objects.filter(assignedDoctorId=doctor.id).count()
#     appointmentcount = models.Appointment.objects.filter(doctorId=doctor.id).count()
#     patientdischarged = models.PatientDischargeDetails.objects.filter(assignedDoctorName=request.user.first_name).count()

#     # STEP 3: Logic for the appointments table
#     # We fetch appointments linked to this specific doctor
#     appointments = models.Appointment.objects.filter(doctorId=doctor.id).order_by('-id')
    
#     # We need to find the specific Patient objects for the pictures/details
#     patient_ids = [a.patientId for a in appointments]
#     patients = models.Patient.objects.filter(id__in=patient_ids)

#     # Create a mapping dictionary to ensure the right patient matches the right appointment
#     patient_dict = {p.id: p for p in patients}
    
#     # Create the zipped list: (Appointment, Patient)
#     appointments_zipped = []
#     for a in appointments:
#         p = patient_dict.get(a.patientId)
#         appointments_zipped.append((a, p))

#     # STEP 4: The Dictionary
#     mydict = {
#         'patientcount': patientcount,
#         'appointmentcount': appointmentcount,
#         'patientdischarged': patientdischarged,
#         'appointments': appointments_zipped,
#         'doctor': doctor,  
#     }
    
#     return render(request, 'hospital/doctor_dashboard.html', context=mydict)



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_patient_view(request):
    mydict={
    'doctor':models.Doctor.objects.get(user_id=request.user.id), #for profile picture of doctor in sidebar
    }
    return render(request,'hospital/doctor_patient.html',context=mydict)

from django.db.models import Q

@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_view_patient_view(request):
    # 1. Get the current doctor
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    doctor_name = doctor.user.first_name  # This should be "Sunil"

    # 2. THE MULTI-PATH FILTER:
    # Path A: Patients assigned to Sunil by ID (Your 7 AI patients)
    # Path B: Patients who have an appointment record with Sunil's name (Your 7 Old patients)
    
    # First, get IDs from the appointment table
    appointment_patient_ids = models.Appointment.objects.filter(
        doctorName__icontains=doctor_name,
        status=True
    ).values_list('patientId', flat=True)

    # Now, combine them into one list
    patients = models.Patient.objects.filter(
        Q(assignedDoctorId=doctor.id) | Q(id__in=appointment_patient_ids),
        status=True
    ).distinct()

    return render(request, 'hospital/doctor_view_patient.html', {
        'patients': patients, 
        'doctor': doctor
    })

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_view_patient_view(request):
#     # 1. Get the current doctor
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # 2. THE MULTI-FILTER:
#     # We look for patients where (Doctor ID matches) OR (ID is null but status is True)
#     # This ensures your AI patients show up AND your old patients show up.
#     patients = models.Patient.objects.filter(
#         Q(assignedDoctorId=doctor.id) | Q(assignedDoctorId__isnull=True),
#         status=True
#     ).distinct()
    
#     return render(request, 'hospital/doctor_view_patient.html', {'patients': patients, 'doctor': doctor})

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor) #this is
# def doctor_view_patient_view(request):
#     # 1. Get the current doctor
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # 2. THE FIX: Get BOTH AI patients and Regular patients
#     # We filter by status=True (Approved) and the assigned doctor
#     patients = models.Patient.objects.all().filter(status=True, assignedDoctorId=doctor.id)
    
#     return render(request, 'hospital/doctor_view_patient.html', {'patients': patients, 'doctor': doctor})


# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_view_patient_view(request):
#     # Initialize the doctor variable as None
#     doctor = None 
    
#     try:
#         # Define the doctor variable
#         doctor = models.Doctor.objects.get(user_id=request.user.id)
#     except models.Doctor.DoesNotExist:
#         # Handle the case where the user isn't correctly linked to a Doctor profile
#         return render(request, 'hospital/doctor_error.html')

#     # Now 'doctor' is guaranteed to have a value
#     patients = models.Patient.objects.all().filter(status=True, assignedDoctorId=doctor.id)
    
#     return render(request, 'hospital/doctor_view_patient.html', {'patients': patients, 'doctor': doctor})

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor) this is
# def doctor_view_patient_view(request):
#     patients = models.Patient.objects.filter(status=True, assignedDoctorId=doctor.id)
#     # patients=models.Patient.objects.all().filter(status=True,assignedDoctorId=request.user.id)
#     doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
#     return render(request,'hospital/doctor_view_patient.html',{'patients':patients,'doctor':doctor})
# hospital/views.py

def view_patient_history_view(request, pk):
    patient = models.Patient.objects.get(id=pk)
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    # This pulls every 'Approved' appointment for this specific patient
    # This is exactly the "Previous List" your boss asked for
    lab_reports = models.LabReport.objects.filter(patient=patient).order_by('-upload_date')
    appointments = models.Appointment.objects.filter(patientId=pk, status=True).order_by('-appointmentDate')
    start_date=request.GET.get('start_date')
    end_date=request.GET.get('end_date')
    # history = models.Prescription.objects.filter(patientId=pk).order_by('-consultationDate')
    history = models.Prescription.objects.filter(
        Q(patientId=pk) | Q(patientName=patient.get_name)
    ).order_by('-consultationDate')

    if start_date and end_date:
        history = history.filter(consultationDate__range=[start_date, end_date])
    
    return render(request, 'hospital/patient_history.html', {
        'patient': patient,
        'appointments': appointments,
        'history': history,
        'doctor': doctor,
        'lab_reports': lab_reports,
        'start_date': start_date,
        'end_date': end_date
    })

# @login_required(login_url='doctorlogin')
# def view_patient_history_view(request, pk):
#     # 1. Get the patient we are looking at
#     patient = models.Patient.objects.get(id=pk)
    
#     # 2. Get history using BOTH the ID and Name from your terminal results
#     # This ensures that ID 8 (Ajay) and ID 9 (Salman) always show their data
    
#     history = models.Prescription.objects.filter(
#         Q(patientId=pk) | Q(patientName=patient.get_name)
#     ).order_by('-consultationDate')

#     # 3. Simplified Date Filter (Only works if you actually use the search box)
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')
    
#     if start_date and end_date:
#         # We only filter if dates are provided; otherwise, we show EVERYTHING
#         history = history.filter(consultationDate__range=[start_date, end_date])

#     return render(request, 'hospital/patient_history.html', {
#         'patient': patient,
#         'history': history,
#         'start_date': start_date,
#         'end_date': end_date
#     })

# @login_required(login_url='doctorlogin')
# def view_patient_history_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # 1. Try to get history by Patient ID
#     history = models.Prescription.objects.filter(patientId=pk).order_by('-consultationDate')

#     # 2. SAFETY CHECK: If no records found by ID, try finding by Name
#     # This fixes the problem where some records show up and others don't
#     if not history.exists():
#         history = models.Prescription.objects.filter(patientName=patient.get_name).order_by('-consultationDate')

#     # 3. Handle the Date Search
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')
#     if start_date and end_date and start_date.strip() != "" and end_date.strip() != "":
#         history = history.filter(consultationDate__range=[start_date, end_date])

#     return render(request, 'hospital/patient_history.html', {
#         'patient': patient,
#         'history': history,
#         'doctor': doctor,
#     })

# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def view_patient_history_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # 1. Get all Approved Appointments (The "Visit List")
#     appointments = models.Appointment.objects.filter(patientId=pk, status=True).order_by('-appointmentDate')
    
#     # 2. Get Medicine History (Prescriptions)
#     # We use patientId=pk. Ensure your Prescription model uses exactly 'patientId'
#     history = models.Prescription.objects.filter(patientId=pk).order_by('-consultationDate')

#     # 3. Handle Date Search (Only filter if BOTH dates are actually typed in)
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')
    
#     if start_date and end_date and start_date != "" and end_date != "":
#         history = history.filter(consultationDate__range=[start_date, end_date])

#     # 4. DEBUG: Print to terminal to see why data might be missing
#     print(f"DEBUG: Found {history.count()} prescriptions for Patient {patient.get_name}")

#     context = {
#         'patient': patient,
#         'appointments': appointments,
#         'history': history,
#         'doctor': doctor,
#         'start_date': start_date,
#         'end_date': end_date
#     }
    
#     return render(request, 'hospital/patient_history.html', context)

# @login_required(login_url='doctorlogin')
# def prescribe_medicine_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)

#     if request.method == 'POST':
#         medicine_data=request.POST.get('medicine', '')
#         symptoms_data=request.POST.get('symptoms', '')
#         notes_data=request.POST.get('notes', '')

#         prescription = models.Prescription(
#             patientId=pk,
#             patientName=patient.get_name,
#             doctorId=doctor.id,
#             doctorName=doctor.get_name,
#             symptoms=symptoms_data,
#             medicine=medicine_data,
#             extra_notes=notes_data,
#             consultationDate=datetime.date.today()
#         )
        
#         if medicine_data:
#             prescription.save()
#             return redirect('prescription-summary', pk=prescription.id)
#             # return redirect('doctor-view-patient')
#         else: 
#             return render(request, 'hospital/prescribe_medicine.html', {'patient':patient, 'error': 'Medicine field cannot be empty!'})
        
#     return render(request, 'hospital/prescribe_medicine.html', {'patient': patient})

# @login_required(login_url='doctorlogin')
# def prescribe_medicine_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)

#     if request.method == 'POST':
#         medicine_names = request.POST.getlist('medicine_name[]')
#         quantities = request.POST.getlist('quantity[]')
#         intervals = request.POST.getlist('interval[]')

#         symptoms_data = request.POST.get('symptoms', '')
#         notes_data = request.POST.get('notes', '')

#         formatted_prescriptions = []
#         for i, name in enumerate(medicine_names, start=1):
#             name = name.strip()
#             if name:
#                 qty = quantities[i-1].strip() or "N/A"
#                 inter = intervals[i-1].strip() or "As directed"
#                 entry = f"{i}. {name} | Qty: {qty} | {inter}"
#                 formatted_prescriptions.append(entry)
#                 # formatted_prescriptions.append(f". {name} | Qty: {qty} | {inter}")

#         final_medicine_string = "\n".join(formatted_prescriptions)

#         if final_medicine_string:  # Check if at least one medicine was added
#             prescription = models.Prescription(
#                 patientId=pk,
#                 patientName=patient.get_name,
#                 doctorId=doctor.id,
#                 doctorName=doctor.get_name,
#                 symptoms=symptoms_data,
#                 medicine=final_medicine_string, # Now saving the formatted list
#                 extra_notes=notes_data,
#                 consultationDate=datetime.date.today()
#             )
#             prescription.save()
#             return redirect('prescription-summary', pk=prescription.id)
#         else: 
#             return render(request, 'hospital/prescribe_medicine.html', {
#                 'patient': patient, 
#                 'error': 'Please add at least one medication using the + button!'
#             })
        
#     return render(request, 'hospital/prescribe_medicine.html', {'patient': patient})

# @login_required(login_url='doctorlogin')
# def prescribe_medicine_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     doctor = models.Doctor.objects.get(user_id=request.user.id)

    

#     if request.method == 'POST':
#         medicine_names = request.POST.getlist('medicine_name[]')
#         quantities = request.POST.getlist('quantity[]')
#         intervals = request.POST.getlist('interval[]')
#         symptoms_data = request.POST.get('symptoms', '')
#         notes_data = request.POST.get('notes', '')

#         # --- DEBUGGING: Check your terminal after clicking save ---
#         print(f"DEBUG: Received Medicine Names: {medicine_names}")
        
#         formatted_prescriptions = []
#         # Use count to handle the 1, 2, 3 numbering
#         count = 1
#         for i in range(len(medicine_names)):
#             name = medicine_names[i].strip()
#             if name:
#                 qty = quantities[i].strip() or "N/A"
#                 inter = intervals[i].strip() or "As directed"
#                 formatted_prescriptions.append(f"{count}. {name} | Qty: {qty} | {inter}")
#                 count += 1

#         final_medicine_string = "\n".join(formatted_prescriptions)
#         print(f"DEBUG: Final String to Save:\n{final_medicine_string}")

#         if final_medicine_string: 
#             prescription = models.Prescription(
#                 patientId=pk,
#                 patientName=patient.get_name,
#                 doctorId=doctor.id,
#                 doctorName=doctor.get_name,
#                 symptoms=symptoms_data,
#                 medicine=final_medicine_string,
#                 extra_notes=notes_data,
#                 consultationDate=datetime.date.today()
#             )
#             prescription.save()
#             print(f"DEBUG: Prescription saved successfully with ID: {prescription.id}")
#             return redirect('prescription-summary', pk=prescription.id)
#         else: 
#             # If we reach here, the form clears because it re-renders with an error
#             print("DEBUG: Logic failed - final_medicine_string was empty.")
#             return render(request, 'hospital/prescribe_medicine.html', {
#                 'patient': patient, 
#                 'error': 'Please add at least one medication!'
#             })
        
#     return render(request, 'hospital/prescribe_medicine.html', {'patient': patient})

@login_required(login_url='doctorlogin')
def prescribe_medicine_view(request, pk):
    patient = models.Patient.objects.get(id=pk)
    doctor = models.Doctor.objects.get(user_id=request.user.id)

    # --- NEW: RENEW & EDIT LOGIC (PRE-FILL DATA) ---
    previous_prescription = models.Prescription.objects.filter(patientId=pk).order_by('-id').first()
    prefilled_medicines = []
    
    if previous_prescription and previous_prescription.medicine:
        # Split the big string by newlines to get individual lines
        lines = previous_prescription.medicine.split('\n')
        for line in lines:
            try:
                # Format expected: "1. Name | Qty: X | Interval"
                # Step 1: Split by '|'
                parts = line.split('|')
                if len(parts) == 3:
                    # Step 2: Remove the "1. " numbering from the name
                    name_part = parts[0].split('.', 1)[1].strip()
                    # Step 3: Remove "Qty: " prefix
                    qty_part = parts[1].replace('Qty:', '').strip()
                    # Step 4: Get interval
                    interval_part = parts[2].strip()
                    
                    prefilled_medicines.append({
                        'name': name_part,
                        'qty': qty_part,
                        'interval': interval_part
                    })
            except Exception as e:
                print(f"DEBUG: Could not parse old line: {line}. Error: {e}")
                continue
    

    if request.method == 'POST':
        medicine_names = request.POST.getlist('medicine_name[]')
        quantities = request.POST.getlist('quantity[]')
        intervals = request.POST.getlist('interval[]')
        symptoms_data = request.POST.get('symptoms', '')
        notes_data = request.POST.get('notes', '')

        print(f"DEBUG: Received Medicine Names: {medicine_names}")
        
        formatted_prescriptions = []
        count = 1
        for i in range(len(medicine_names)):
            name = medicine_names[i].strip()
            if name:
                qty = quantities[i].strip() or "N/A"
                inter = intervals[i].strip() or "As directed"
                formatted_prescriptions.append(f"{count}. {name} | Qty: {qty} | {inter}")
                count += 1

        final_medicine_string = "\n".join(formatted_prescriptions)

        if final_medicine_string: 
            prescription = models.Prescription(
                patientId=pk,
                patientName=patient.get_name,
                doctorId=doctor.id,
                doctorName=doctor.get_name,
                symptoms=symptoms_data,
                medicine=final_medicine_string,
                extra_notes=notes_data,
                consultationDate=date.today()
            )
            prescription.save()
            return redirect('prescription-summary', pk=prescription.id)
        else: 
            return render(request, 'hospital/prescribe_medicine.html', {
                'patient': patient, 
                'prefilled_medicines': prefilled_medicines, # Pass back on error
                'error': 'Please add at least one medication!'
            })
        
    return render(request, 'hospital/prescribe_medicine.html', {
        'patient': patient,
        'prefilled_medicines': prefilled_medicines  # Pass to template for GET request
    })

@login_required(login_url='doctorlogin')
def  prescription_summary_view(request, pk):
    try:
        prescription = models.Prescription.objects.get(id=pk)
        return render(request, 'hospital/prescription_summary.html', {'prescription': prescription})
    except models.Prescription.DoesNotExist:
        return HttpResponse("Error: Prescription Record not found in the database.")   


@login_required(login_url='doctorlogin')
def download_prescription_pdf(request, pk):
    prescription = get_object_or_404(models.Prescription, id=pk)
    data = {
        'prescription': prescription,
        'hospital_name': 'CITY GENERAL HOSPITAL'
    }
    pdf = render_to_pdf('hospital/prescription_pdf_template.html', data)
    return pdf


# hospital/views.py
def view_patient_history_view(request, pk):
    patient = models.Patient.objects.get(id=pk)
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    
    # Get date values from the GET request (the search form)
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Start with all prescriptions for this patient
    history = models.Prescription.objects.filter(patientId=pk).order_by('-consultationDate')
    
    # Apply filters if dates are provided
    if start_date and end_date:
        history = history.filter(consultationDate__range=[start_date, end_date])
    
    return render(request, 'hospital/patient_history.html', {
        'patient': patient,
        'history': history,
        'doctor': doctor,
        'start_date': start_date,
        'end_date': end_date
    })

from django.utils import timezone


@login_required(login_url='doctorlogin')
def doctor_calendar_events_view(request):
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    
    
    # Use the SAME "Wide Search" that worked for your dashboard
    appointments = models.Appointment.objects.filter(
        Q(doctorId=doctor.id) | 
        Q(doctorId=request.user.id) | 
        Q(doctorName=request.user.first_name)
        # Q(doctorName__icontains=request.user.first_name) |
        # Q(doctorName__icontains=doctor.get_name)
        # Q(doctorName__icontains=request.user.last_name)

    )
    
    events = []
    for a in appointments:
        # We check if appointmentDate exists to prevent errors
        if a.appointmentDate:
            start_time = a.appointmentDate.strftime('%Y-%m-%dT%H:%M:%S')

            from datetime import timedelta
            end_time = (a.appointmentDate + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S')

            events.append({
                # 'id': a.id,
                'title': f"Patient: {a.patientName}",
                # 'start': a.appointmentDate.isoformat(), # Converts date to string FullCalendar likes
                # 'start': a.appointmentDate.strftime('%Y-%m-%d'),
                'start': start_time,
                'end': end_time,
                'description': a.description,
                'allDay': False,
                'backgroundColor': '#28a745' if a.status else '#ffc107', # Green if approved, Yellow if pending
                'borderColor': '#1e7e34'
            })
            
    return JsonResponse(events, safe=False)

# @login_required(login_url='doctorlogin')
# def doctor_calendar_events_view(request):
#     # 1. Fetch ALL appointments to bypass the broken doctorId filter
#     # This guarantees Ranveer (16) and Ramesh (15) appear.
#     appointments = models.Appointment.objects.all()

#     # 2. DEBUG: This will print the actual count in your terminal
#     print(f"--- CALENDAR DEBUG: TOTAL FOUND: {appointments.count()} ---")

#     events = []
#     for a in appointments:
#         # Check if the date exists to prevent the 'NoneType' error
#         if a.appointmentDate:
#             # Format date as 'YYYY-MM-DD' for FullCalendar compatibility
#             date_str = a.appointmentDate.strftime('%Y-%m-%d')
            
#             events.append({
#                 'id': a.id,
#                 'title': f"Pt: {a.patientName}",
#                 'start': date_str,
#                 'allDay': True, # This makes the event span the whole day box
#                 'description': a.description or "No description",
#                 'backgroundColor': '#28a745' if a.status else '#ffc107',
#                 'borderColor': '#1e7e34',
#                 'textColor': 'white'
#             })
#             print(f"--- CALENDAR DEBUG: Adding {a.patientName} for {date_str} ---")
            
#     return JsonResponse(events, safe=False)



# def doctor_calendar_view(request):
#     return render(request, 'hospital/doctor_calendar.html')



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_calendar_view(request):
    return render(request, 'hospital/doctor_calendar.html')

@login_required(login_url='doctorlogin')
def doctor_calendar_events(request):
    try:
        doctor = models.Doctor.objects.get(user_id=request.user.id)
        
        # Clean the name: Remove '@' and get just the name (e.g., 'sunil')
        search_name = request.user.username.replace('@', '').strip()
        
        # Fuzzy match using doctorId OR the cleaned username
        appointments = models.Appointment.objects.filter(
            Q(doctorId=doctor.id) | 
            Q(doctorName__icontains=search_name),
            status=True
        )

        events = []
        for a in appointments:
            # 1. Check if the database has the date and time
            if a.appointmentDate:
                # We use the ISO format 'T' that FullCalendar requires
                # Example result: "2026-03-05T18:00:00"
                start_datetime = a.appointmentDate.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Fallback if the field is empty
                start_datetime = f"{date.today()}T09:00:00"

            # 2. Add to the list
            events.append({
                'title': f"Pt: {a.patientName}",
                'start': start_datetime, # This now contains your 06:00 PM!
                'description': a.description,
                'allDay': False,
                'backgroundColor': '#2c3e50' if not a.patientId else '#3788d8',
                'borderColor': '#1a252f'
            })
        
        return JsonResponse(events, safe=False)
    
    except Exception as e:
        print(f"Calendar Error: {e}")
        return JsonResponse([], safe=False)

# @login_required(login_url='doctorlogin')
# def doctor_calendar_events(request):
#     doctor = models.Doctor.objects.get(user_id=request.user.id)
    
#     # Fuzzy match to include "Arjun", "Kina", etc.
#     appointments = models.Appointment.objects.filter(
#         Q(doctorId=doctor.id) | 
#         Q(doctorName__icontains=doctor.get_name.strip()),
#         status=True
#     )

#     events = []
#     for a in appointments:
#         # 1. Get the base date (YYYY-MM-DD)
#         date_str = a.appointmentDate.strftime("%Y-%m-%d")
        
#         # 2. Extract time from description (e.g., "10:00 AM")
#         # Default to 09:00:00 if no time is found
#         time_str = "09:00:00" 
#         if "Time:" in a.description:
#             try:
#                 # Extracts "10:00 AM" from "Mobile: ... | Time: 10:00 AM | ..."
#                 raw_time = a.description.split("Time:")[1].split("|")[0].strip()
#                 # Convert "10:00 AM" to "10:00:00" (24hr format)
#                 t_obj = datetime.datetime.strptime(raw_time, "%I:%M %p")
#                 time_str = t_obj.strftime("%H:%M:%S")
#             except:
#                 pass 

#         # 3. Combine Date and Time for FullCalendar (ISO format)
#         start_datetime = f"{date_str}T{time_str}"

#         events.append({
#             'title': f"Pt: {a.patientName}",
#             'start': start_datetime,
#             'description': a.description,
#             'allDay': False, # This forces it to show at a specific time
#             'color': '#3788d8' if a.patientId else '#2c3e50'
#         })
    
#     return JsonResponse(events, safe=False)

@login_required(login_url='doctorlogin')
def upload_lab_report_view(request, pk):
    patient = models.Patient.objects.get(id=pk)
    if request.method == 'POST':
        report = models.LabReport(
            patient=patient,
            report_type=request.POST.get('report_type'),
            description=request.POST.get('description'),
            report_file=request.FILES.get('report_file'), # Note: request.FILES is used for files
            doctor_notes=request.POST.get('notes')
        )
        report.save()
        return redirect('patient-history', pk=pk)
    
    return render(request, 'hospital/upload_lab_report.html', {'patient': patient})

# @login_required(login_url='doctorlogin')
# def patient_history_timeline_view(request, pk):
#     patient = models.Patient.objects.get(id=pk)
#     history = models.PatientHistory.objects.filter(patient=patient).order_by('-visit_date')

#     return render(request, 'hospital/patient_history_timeline.html', {
#         'patient': patient,
#         'history': history,
#     })

@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def search_view(request):
    doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
    # whatever user write in search box we get in query
    query = request.GET['query']
    patients=models.Patient.objects.all().filter(status=True,assignedDoctorId=request.user.id).filter(Q(symptoms__icontains=query)|Q(user__first_name__icontains=query))
    return render(request,'hospital/doctor_view_patient.html',{'patients':patients,'doctor':doctor})



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_view_discharge_patient_view(request):
    dischargedpatients=models.PatientDischargeDetails.objects.all().distinct().filter(assignedDoctorName=request.user.first_name)
    doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
    return render(request,'hospital/doctor_view_discharge_patient.html',{'dischargedpatients':dischargedpatients,'doctor':doctor})



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_appointment_view(request):
    doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
    return render(request,'hospital/doctor_appointment.html',{'doctor':doctor})



# @login_required(login_url='doctorlogin')
# @user_passes_test(is_doctor)
# def doctor_view_appointment_view(request):
    # doctor=models.Doctor.objects.get(user_id=request.user.id) 
    # appointments=models.Appointment.objects.filter(doctorId=request.user.id, status=False)
    # # appointments = models.Appointment.objects.filter(doctorId=doctor.id)

    # patientid=[]
    # for a in appointments:
    #     patientid.append(a.patientId)

    # patients=models.Patient.objects.all().filter(status=True,user_id__in=patientid)

    # appointments_data= zip(appointments, patients)
    # return render(request,'hospital/doctor_view_appointment.html',{'appointments':appointments_data,'doctor':doctor})

    
    # doctor = models.Doctor.objects.get(user_id=request.user.id)
    
    
    # appointments = models.Appointment.objects.filter(
    #     Q(doctorId=doctor.id) | 
    #     Q(doctorId=request.user.id) | 
    #     Q(doctorName=request.user.first_name)
    # ).order_by('-id')
    

    # appointment_list = []
    # for a in appointments:
    #     try:
    #         p = models.Patient.objects.get(id=a.patientId)
    #     except models.Patient.DoesNotExist:
    #         p = None
    #     appointment_list.append((a, p))
    
    # return render(request, 'hospital/doctor_view_appointment.html', {
    #     'appointments': appointment_list,
    #     'doctor': doctor
    # })


@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_view_appointment_view(request):
    # 1. Get the doctor object
    doctor = models.Doctor.objects.get(user_id=request.user.id)
    
    # 2. Flexible Filter Logic
    # This captures appointments by numeric ID OR by the "Dr. Janu Manu" name string
    # We use doctor.get_name to match the "Dr. janu" profile you have
    appointments = models.Appointment.objects.filter(
        Q(doctorId=doctor.id) | 
        Q(doctorId=request.user.id) | 
        Q(doctorName__icontains=doctor.get_name.strip()) |
        Q(doctorName__icontains=request.user.first_name)
    ).order_by('-id')

    # 3. Build the appointment list (handling AI patients with no Patient ID)
    appointment_list = []
    for a in appointments:
        # We use filter().first() instead of get() to safely handle AI "Walk-in" cases
        # AI appointments usually have patientId=None, so this will return None gracefully
        p = models.Patient.objects.filter(id=a.patientId).first()
        appointment_list.append((a, p))
    
    return render(request, 'hospital/doctor_view_appointment.html', {
        'appointments': appointment_list,
        'doctor': doctor
    })



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def doctor_delete_appointment_view(request):
    doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
    appointments=models.Appointment.objects.all().filter(status=True,doctorId=request.user.id)
    patientid=[]
    for a in appointments:
        patientid.append(a.patientId)
    patients=models.Patient.objects.all().filter(status=True,user_id__in=patientid)
    appointments=zip(appointments,patients)
    return render(request,'hospital/doctor_delete_appointment.html',{'appointments':appointments,'doctor':doctor})



@login_required(login_url='doctorlogin')
@user_passes_test(is_doctor)
def delete_appointment_view(request,pk):
    appointment=models.Appointment.objects.get(id=pk)
    appointment.delete()
    doctor=models.Doctor.objects.get(user_id=request.user.id) #for profile picture of doctor in sidebar
    appointments=models.Appointment.objects.all().filter(status=True,doctorId=request.user.id)
    patientid=[]
    for a in appointments:
        patientid.append(a.patientId)
    patients=models.Patient.objects.all().filter(status=True,user_id__in=patientid)
    appointments=zip(appointments,patients)
    return render(request,'hospital/doctor_delete_appointment.html',{'appointments':appointments,'doctor':doctor})



#---------------------------------------------------------------------------------
#------------------------ DOCTOR RELATED VIEWS END ------------------------------
#---------------------------------------------------------------------------------






#---------------------------------------------------------------------------------
#------------------------ PATIENT RELATED VIEWS START ------------------------------
#---------------------------------------------------------------------------------
@login_required(login_url='patientlogin')
@user_passes_test(is_patient)
def patient_dashboard_view(request):
    patient=models.Patient.objects.get(user_id=request.user.id)
    doctor=models.Doctor.objects.get(user_id=patient.assignedDoctorId)
    mydict={
    'patient':patient,
    'doctorName':doctor.get_name,
    'doctorMobile':doctor.mobile,
    'doctorAddress':doctor.address,
    'symptoms':patient.symptoms,
    'doctorDepartment':doctor.department,
    'admitDate':patient.admitDate,
    }
    return render(request,'hospital/patient_dashboard.html',context=mydict)



@login_required(login_url='patientlogin')
@user_passes_test(is_patient)
def patient_appointment_view(request):
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar
    return render(request,'hospital/patient_appointment.html',{'patient':patient})



@login_required(login_url='patientlogin')
@user_passes_test(is_patient)
def patient_book_appointment_view(request):
    appointmentForm=forms.PatientAppointmentForm()
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar

    message=None

    mydict = { 
        'appointmentForm':appointmentForm,
        'patient':patient,
        'message':message,
        }
    

    if request.method=='POST':
        appointmentForm=forms.PatientAppointmentForm(request.POST)
        if appointmentForm.is_valid():
            print(request.POST.get('doctorId'))
            desc=request.POST.get('description')

            doctor=models.Doctor.objects.get(user_id=request.POST.get('doctorId'))
            
            appointment=appointmentForm.save(commit=False)
            appointment.doctorId=request.POST.get('doctorId')
            appointment.patientId=request.user.id #----user can choose any patient but only their info will be stored
            appointment.doctorName=models.User.objects.get(id=request.POST.get('doctorId')).first_name
            appointment.patientName=request.user.first_name #----user can choose any patient but only their info will be stored
            appointment.status=False
            appointment.save()
        return HttpResponseRedirect('patient-view-appointment')
    return render(request,'hospital/patient_book_appointment.html',context=mydict)



def patient_view_doctor_view(request):
    doctors=models.Doctor.objects.all().filter(status=True)
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar
    return render(request,'hospital/patient_view_doctor.html',{'patient':patient,'doctors':doctors})



def search_doctor_view(request):
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar
    
    # whatever user write in search box we get in query
    query = request.GET['query']
    doctors=models.Doctor.objects.all().filter(status=True).filter(Q(department__icontains=query)| Q(user__first_name__icontains=query))
    return render(request,'hospital/patient_view_doctor.html',{'patient':patient,'doctors':doctors})




@login_required(login_url='patientlogin')
@user_passes_test(is_patient)
def patient_view_appointment_view(request):
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar
    appointments=models.Appointment.objects.all().filter(patientId=request.user.id)
    return render(request,'hospital/patient_view_appointment.html',{'appointments':appointments,'patient':patient})



@login_required(login_url='patientlogin')
@user_passes_test(is_patient)
def patient_discharge_view(request):
    patient=models.Patient.objects.get(user_id=request.user.id) #for profile picture of patient in sidebar
    dischargeDetails=models.PatientDischargeDetails.objects.all().filter(patientId=patient.id).order_by('-id')[:1]
    patientDict=None
    if dischargeDetails:
        patientDict ={
        'is_discharged':True,
        'patient':patient,
        'patientId':patient.id,
        'patientName':patient.get_name,
        'assignedDoctorName':dischargeDetails[0].assignedDoctorName,
        'address':patient.address,
        'mobile':patient.mobile,
        'symptoms':patient.symptoms,
        'admitDate':patient.admitDate,
        'releaseDate':dischargeDetails[0].releaseDate,
        'daySpent':dischargeDetails[0].daySpent,
        'medicineCost':dischargeDetails[0].medicineCost,
        'roomCharge':dischargeDetails[0].roomCharge,
        'doctorFee':dischargeDetails[0].doctorFee,
        'OtherCharge':dischargeDetails[0].OtherCharge,
        'total':dischargeDetails[0].total,
        }
        print(patientDict)
    else:
        patientDict={
            'is_discharged':False,
            'patient':patient,
            'patientId':request.user.id,
        }
    return render(request,'hospital/patient_discharge.html',context=patientDict)


# from django.shortcuts import render, redirect
# from . import models  # Or 'from .models import Appointment'

def emergency_admission(request, name): # Receives name from URL
    # Use name from URL, fallback to 'Patient' if empty
    patient_name = name if name else "Patient"
    mobile = request.session.get('temp_mobile', 'N/A')
    
    # Create the Emergency Appointment
    models.Appointment.objects.create(
        patientName=patient_name,
        mobile=mobile,
        doctorName="EMERGENCY WARD",
        appointmentDate=date.today(),
        description="🚨 CRITICAL: Immediate Emergency Admission",
        status=True 
    )

    success_message = f"Patient {patient_name} has been added to the Emergency Ward. Don't panic, we will try our best for this emergency."
    
    return render(request, 'hospital/emergency_success.html', {
        'name': patient_name,
        'mssg': success_message
    })

# def emergency_admission(request):
#     # 1. Retrieve the LATEST patient info from the current session
#     # We use .get() to avoid errors if the session is empty
#     name = request.session.get('temp_name', 'the patient')
#     mobile = request.session.get('temp_mobile', 'N/A')
    
#     # 2. Create the Emergency Appointment
#     models.Appointment.objects.create(
#         patientName=name,
#         mobile=mobile,
#         doctorName="EMERGENCY WARD",
#         appointmentDate=datetime.date.today(),
#         description="🚨 CRITICAL: Immediate Emergency Admission (Trauma Team Alerted)",
#         status=True 
#     )

#     # 3. Prepare the message
#     # If name is Ronny, it will now correctly say "Patient Ronny..."
#     success_message = f"Patient {name} has been added to the Emergency Ward. Don't panic, we will try our best for this emergency. Our trauma team is alerted."

#     # 4. CLEAR the temp session names so the next patient starts fresh
#     # This prevents 'Nehal' from appearing when 'Ronny' is the one in trouble
#     if 'temp_name' in request.session:
#         del request.session['temp_name']
    
#     return render(request, 'hospital/emergency_success.html', {
#         'name': name,
#         'mssg': success_message
#     })

# def emergency_admission(request):
#     # 1. Retrieve Patient info from session
#     name = request.session.get('temp_name', 'Patient')
#     mobile = request.session.get('temp_mobile', 'N/A')
    
#     # 2. Automatically log this in the Appointment table as EMERGENCY
#     # This ensures the doctors see the emergency alert immediately
#     models.Appointment.objects.create(
#         patientName=name,
#         mobile=mobile,
#         doctorName="EMERGENCY WARD",
#         appointmentDate=datetime.date.today(),
#         description="🚨 CRITICAL: Immediate Emergency Admission (Trauma/Broken Limb)",
#         status=True 
#     )

#     # 3. Render the specialized emergency message
#     return render(request, 'hospital/emergency_success.html', {
#         'name': name,
#         'mssg': f"Patient {name} has been added to the Emergency Ward. Don't panic, we will try our best for this emergency. Our trauma team is alerted."
#     })

#============================================================================



def confirm_appointment(request):
    if request.method == 'POST':
        # 1. Retrieve Data
        name = request.POST.get('name') or request.session.get('temp_name')
        raw_doctor_name = request.POST.get('doctor_name', '')
        time_slot = str(request.POST.get('time_slot', '')).strip()
        symptoms = request.POST.get('symptom') or request.session.get('temp_symptoms')
        mobile_num = request.POST.get('mobile')
        user_address = request.POST.get('address')
        user_date = request.POST.get('appointment_date', '').strip()

        if not name or not mobile_num:
            return redirect('/book-appointment/?error=missing_info')

        if not user_date or user_date == "None" or user_date == "":
            user_date = str(date.today())

        # 2. DOCTOR ROUTING LOGIC
        clean_name = raw_doctor_name.lower()
        if "vikas" in clean_name:
            doctor_name = "Dr. Vikas Gupta"; doc_id = 4
        elif "sunil" in clean_name:
            doctor_name = "Dr. Sunil Rajendran"; doc_id = 10
        elif "janu" in clean_name or "manu" in clean_name:
            doctor_name = "Dr. Janu Manu"; doc_id = 9  
        elif "amit" in clean_name:
            doctor_name = "Dr. Amit Patel"; doc_id = 8
        elif "chetan" in clean_name:
            doctor_name = "Dr. Chetan Raj"; doc_id = 7
        elif "prakash" in clean_name:
            doctor_name = "Dr. Prakash Raj"; doc_id = 5
        elif "baghel" in clean_name:
            doctor_name = "Dr. Baghel Kadre"; doc_id = 3
        else:
            doctor_name = "Dr. Sunil Rajendran"; doc_id = 10

        # 3. Time Formatting (Fixes Calendar Overlap)
        # We assign exact hours so the calendar can separate Paresh and Simon
        time_map = {
            "10:00 AM": "10:00:00",
            "11:00 AM": "11:00:00",
            "12:00 PM": "12:00:00",
            "02:00 PM": "14:00:00",
            "03:00 PM": "15:00:00",
            "04:00 PM": "16:00:00",
            "06:00 PM": "18:00:00",
            "07:00 PM": "19:00:00",
            "08:00 PM": "20:00:00",
        }
        
        hour_val = time_map.get(time_slot, "12:00:00")
        full_dt_string = f"{user_date} {hour_val}"
        
        try:
            final_appointment_dt = datetime.strptime(full_dt_string, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            final_appointment_dt = datetime.now()

        # 4. Save to Database
        try:
            models.Appointment.objects.create(
                patientId=1,      
                doctorId=doc_id,   
                patientName=name,
                doctorName=doctor_name,
                appointmentDate=final_appointment_dt, 
                # This ensures the dashboard shows "Slot: 06:00 PM | Symptoms: Fungal infection"
                description=f"Slot: {time_slot} | Symptoms: {symptoms}", 
                mobile=mobile_num,
                address=user_address,
                status=True
            )
            
            # 5. Success Response
            return render(request, 'hospital/index.html', {
                'booked_success': True,
                'name': name,
                'doctor': doctor_name,
                'time': time_slot,
                'date': user_date
            })

        except IntegrityError:
            messages.error(request, f"Sorry, {doctor_name} is already booked for {time_slot} on {user_date}.")
            return redirect('/book-appointment/')

    return redirect('/')







# def confirm_appointment(request):
#     if request.method == 'POST': #original original
#         # 1. Retrieve Data
#         name = request.POST.get('name') or request.session.get('temp_name')
#         raw_doctor_name = request.POST.get('doctor_name', '')
#         time_slot = str(request.POST.get('time_slot', '')).strip()
#         symptoms = request.POST.get('symptom') or request.session.get('temp_symptoms')
#         mobile_num = request.POST.get('mobile')
#         user_address = request.POST.get('address')

#         if not name or not mobile_num:
#             return redirect('/book-appointment/?error=missing_info')

#         # --- Ensure date is NOT empty ---
#         user_date = request.POST.get('appointment_date', '').strip()
#         if not user_date or user_date == "None" or user_date == "":
#             user_date = str(date.today())

#         # 2. DOCTOR ROUTING LOGIC (The 100% Fix)
#         # Use lowercase check to be safe with name formats
#         clean_name = raw_doctor_name.lower()
        
#         if "vikas" in clean_name:
#             doctor_name = "Dr. Vikas Gupta"
#             doc_id = 4
#         elif "sunil" in clean_name:
#             doctor_name = "Dr. Sunil Rajendran"
#             doc_id = 10
#         elif "janu" in clean_name or "manu" in clean_name:
#             doctor_name = "Dr. Janu Manu"
#             doc_id = 9  
#         elif "amit" in clean_name:
#             doctor_name = "Dr. Amit Patel"
#             doc_id = 8
#         elif "chetan" in clean_name:
#             doctor_name = "Dr. Chetan Raj"
#             doc_id = 7
#         elif "prakash" in clean_name:
#             doctor_name = "Dr. Prakash Raj"
#             doc_id = 5
#         elif "baghel" in clean_name:
#             doctor_name = "Dr. Baghel Kadre"
#             doc_id = 3
#         else:
#             doctor_name = "Dr. Sunil Rajendran" # Default fallback
#             doc_id = 10

#         # 3. Time Formatting
#         if "Morning" in time_slot:
#             hour_val = "10:00:00"
#         elif "Afternoon" in time_slot:
#             hour_val = "15:00:00"
#         elif "Evening" in time_slot:
#             hour_val = "18:00:00"
#         elif "IMMEDIATE" in time_slot:
#             hour_val = "08:00:00"
#         else:
#             hour_val = "12:00:00"

#         full_dt_string = f"{user_date} {hour_val}"

#         try:
#             final_appointment_dt = datetime.strptime(full_dt_string, "%Y-%m-%d %H:%M:%S")
#         except ValueError:
#             final_appointment_dt = datetime.now()

#         # 4. Save to Database
#         models.Appointment.objects.create(
#             patientId=1,      
#             doctorId=doc_id,   # Links to Vikas (4) or Sunil (10)
#             patientName=name,
#             doctorName=doctor_name,
#             appointmentDate=final_appointment_dt, 
#             description=f"Slot: {time_slot} | Symptoms: {symptoms}",
#             mobile=mobile_num,
#             address=user_address,
#             status=True
#         )

#         # 5. Success Response
#         return render(request, 'hospital/index.html', {
#             'booked_success': True,
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot,
#             'date': user_date
#         })

#     return redirect('/')

# def confirm_appointment(request):
#     if request.method == 'POST': #original 3
#         # 1. Retrieve Data
#         name = request.session.get('temp_name', 'Guest Patient')
#         raw_doctor_name = request.POST.get('doctor_name', '')
#         time_slot = str(request.POST.get('time_slot', '')).strip()
#         symptoms = request.session.get('temp_symptoms', 'No symptoms provided')
#         mobile_num = request.POST.get('mobile', '0000000000')

#         # --- FIX: Ensure date is NOT empty ---
#         user_date = request.POST.get('appointment_date', '').strip()
#         if not user_date or user_date == "None":
#             user_date = str(datetime.date.today()) # Fallback to today's date

#         # 2. Match Doctor ID 4
#         if "vikas gupta" in raw_doctor_name.lower():
#             doctor_name = "Dr. vikas gupta"
#             doc_id = 4
#         else:
#             doctor_name = raw_doctor_name
#             doc_id = 1

#         # 3. Assign Hour (Cleaned of all extra spaces)
#         if "Morning" in time_slot:
#             hour_val = "10:00:00"
#         elif "Afternoon" in time_slot:
#             hour_val = "15:00:00"
#         elif "Evening" in time_slot:
#             hour_val = "18:00:00"
#         elif "IMMEDIATE" in time_slot:
#             hour_val = "08:00:00"
#         else:
#             hour_val = "12:00:00"

#         # 4. Create the final timestamp string
#         # Result: "2026-02-19 08:00:00"
#         full_dt_string = f"{user_date} {hour_val}"

#         # 5. Save to Database
#         models.Appointment.objects.create(
#             patientId=1,      
#             doctorId=doc_id,   
#             patientName=name,
#             doctorName=doctor_name,
#             appointmentDate=full_dt_string, 
#             description=f"Slot: {time_slot} | Symptoms: {symptoms}",
#             mobile=mobile_num,
#             status=True
#         )

#         return render(request, 'hospital/index.html', {
#             'booked_success': True,
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot,
#             'date': user_date
#         })

#     return redirect('/')

# def confirm_appointment(request):
#     if request.method == 'POST': #original 2
#         # 1. Retrieve info
#         name = request.session.get('temp_name', 'Patient')
#         doctor_name = request.POST.get('doctor_name')
#         time_slot = request.POST.get('time_slot')
#         user_date = request.POST.get('appointment_date')
#         symptoms = request.session.get('temp_symptoms', '')

#         # 2. Assign exact Hour (24-hour format)
#         if "Morning" in str(time_slot):
#             hour_val = "10:00:00"
#         elif "Afternoon" in str(time_slot):
#             hour_val = "15:00:00"
#         elif "Evening" in str(time_slot):
#             hour_val = "18:00:00" # 6 PM
#         else:
#             hour_val = "12:00:00"

#         # 3. Create the final timestamp string
#         # Result: "2026-02-18 18:00:00"
#         full_dt_string = f"{user_date} {hour_val}"

#         # 4. Save to Database
#         models.Appointment.objects.create(
#             patientName=name,
#             doctorName=doctor_name,
#             appointmentDate=full_dt_string, # Django will save this exactly because USE_TZ=False
#             description=f"Slot: {time_slot} | Symptoms: {symptoms}",
#             status=True
#         )

#         # 5. Redirect to success (staying on index to keep widget open)
#         return render(request, 'hospital/booking_success.html', {
#             'booked_success': True,
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot,
#             'date': user_date
#         })

#     return redirect('/')


# def confirm_appointment(request):
#     if request.method == 'POST': #original 1
#         # 1. Retrieve info from session
#         name = request.session.get('temp_name', 'Walk-in Patient')
#         mobile = request.session.get('temp_mobile', 'N/A')
#         symptoms = request.session.get('temp_symptoms', 'General AI Consultation')
        
#         # 2. Extract Data from Form
#         doctor_name = request.POST.get('doctor_name') 
#         time_slot = request.POST.get('time_slot')
        
#         # 3. Create Appointment in Database
#         models.Appointment.objects.create(
#             patientName=name,
#             mobile=mobile,
#             doctorName=doctor_name,
#             appointmentDate=datetime.datetime.now(), # Using current timestamp
#             description=f"Time: {time_slot} | Symptoms: {symptoms}",  
#             status=True 
#         )
        
#         # 4. Success redirect
#         return render(request, 'hospital/booking_success.html', {
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot
#         })

#     return redirect('chatbot_url')

# def confirm_appointment(request):
#     if request.method == 'POST':
#         # 1. Retrieve Patient info from session
#         name = request.session.get('temp_name', 'Walk-in Patient')
#         mobile = request.session.get('temp_mobile', 'N/A')
        
#         # 2. Extract Data from Session and Form
#         ai_data = request.session.get('last_ai_prescription', {})
#         doctor_notes = ai_data.get('raw_symptoms', 'General AI Consultation') 
        
#         doctor_name = request.POST.get('doctor_name') # Gets "Dr. Janu Manu" from the button
#         time_slot = request.POST.get('time_slot')
        
#         # 3. Create Appointment in Database
#         # This will now show "Dr. Janu Manu" in the Doctor Name column
#         models.Appointment.objects.create(
#             patientName=name,
#             mobile=mobile,
#             doctorName=doctor_name,
#             appointmentDate=datetime.date.today(),
#             description=f"Time: {time_slot} | Symptoms: {doctor_notes}",  
#             status=True 
#         )
        
#         # 4. Success redirect
#         return render(request, 'hospital/booking_success.html', {
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot
#         })

#     return redirect('chatbot_url')

# def confirm_appointment(request):
#     if request.method == 'POST':
#         # 1. Retrieve Patient info from session
#         name = request.session.get('temp_name', 'Walk-in Patient')
#         mobile = request.session.get('temp_mobile', 'N/A')
        
#         # 2. Extract Data
#         ai_data = request.session.get('last_ai_prescription', {})
        
#         # Pulling the cleaned raw symptoms we saved in the chatbot_page
#         doctor_notes = ai_data.get('raw_symptoms', 'General AI Consultation') 
        
#         # 3. Get selection from form
#         doctor_name = request.POST.get('doctor_name')
#         time_slot = request.POST.get('time_slot')
        
#         # 4. Create Appointment
#         # This writes the record to the database for the Doctor Dashboard
#         models.Appointment.objects.create(
#             patientName=name,
#             mobile=mobile,
#             doctorName=doctor_name,
#             appointmentDate=datetime.date.today(),
#             description=doctor_notes,  
#             status=True 
#         )
        
#         # 5. Success redirect
#         return render(request, 'hospital/booking_success.html', {
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot
#         })

#     # --- THE FIX FOR THE VALUEERROR ---
#     # If the request is NOT a POST (e.g., someone just types the URL), 
#     # we redirect them back to the chatbot to start over.
#     return redirect('chatbot_url')

# def confirm_appointment(request):
#     if request.method == 'POST':
#         # 1. Retrieve Patient info from session
#         name = request.session.get('temp_name', 'Walk-in Patient')
#         mobile = request.session.get('temp_mobile', 'N/A')
        
#         # 2. Extract Data
#         ai_data = request.session.get('last_ai_prescription', {})
        
#         # We use 'raw_symptoms' for the doctor's table description
#         # This ensures the table shows "intense back pain" instead of "General Consultation"
#         doctor_notes = ai_data.get('raw_symptoms', 'General AI Consultation') 
        
#         # 3. Get selection from form
#         doctor_name = request.POST.get('doctor_name')
#         time_slot = request.POST.get('time_slot')
        
#         # 4. Create Appointment
#         models.Appointment.objects.create(
#             patientName=name,
#             mobile=mobile,
#             doctorName=doctor_name,
#             appointmentDate=datetime.date.today(),
#             description=doctor_notes,  # This now stores the actual symptom typed
#             status=True 
#         )
        
#         # 5. Success redirect
#         return render(request, 'hospital/booking_success.html', {
#             'name': name,
#             'doctor': doctor_name,
#             'time': time_slot
#         })

# ============================================================================

# Initialize the bot once
bot = MedicalChatbot()

def chat_response(request):
    user_input = request.GET.get('msg', '').strip()
    if not user_input:
        return JsonResponse({'response': "Hello! Please describe your symptoms."})

    
    
    if 'chat_state' not in request.session or not request.session['chat_state']:
        request.session['chat_state'] = {
            'step': 'INITIAL',
            'yes_list': [],
            'no_list': [],
            'active_q': None
        }

    state = request.session['chat_state']
    bot.possible_diseases = bot.dataset.copy()

    for s in state['yes_list']: bot.filter_diseases(s, True)
    for s in state['no_list']: bot.filter_diseases(s, False)
    bot.active_symptoms = state['yes_list'] + state['no_list']

    if state['step'] == 'INITIAL':
        matched = bot.get_symptom_from_text(user_input)
        if matched:
            state['yes_list'].append(matched)
            bot.filter_diseases(matched, True)
            bot.active_symptoms.append(matched)
            state['step'] = 'DIAGNOSING'
            next_q = bot.get_next_question()
            state['active_q'] = next_q
            response = f"I've identified <b>{matched.replace('_',' ')}</b>. Do you also have <b>{next_q}</b>?"
        else:
            response = "I couldn't match that. Describe it differently?"

    elif state['step'] == 'DIAGNOSING':
        current_symptom = state['active_q'].replace(' ', '_')
        user_answer = user_input.lower()
        

        if 'yes' in user_answer:
            if current_symptom not in state['yes_list']:
                state['yes_list'].append(current_symptom)
        else:
            if current_symptom not in state['no_list']:
                state['no_list'].append(current_symptom)
        
        bot.active_symptoms = state['yes_list'] + state['no_list']

        bot.possible_diseases = bot.dataset.copy()
        for s in state['yes_list']: bot.filter_diseases(s, has_symptom=True)
        for s in state['no_list']: bot.filter_diseases(s, has_symptom=False)

        unique_count = bot.possible_diseases['Disease'].nunique()
        
        if unique_count <= 1:
            result = bot.get_final_diagnosis()
            response = f"Based on clinical data, you may have <b>{result['disease']}</b>.<br><br>{result['description']}"

            request.session['chat_state'] = None # Clear session when finished
            return JsonResponse({
            'response': response,
            'precautions': result.get('precautions', []), # Pass the list here
            'is_final': True # A flag to tell the wrapper "we are done"
        })
        else:
            next_q = bot.get_next_question()
            state['active_q'] = next_q
            response = f"Understood. Are you experiencing <b>{next_q}</b>?"

    request.session.modified = True
    return JsonResponse({'response': response})









# def chat_response(request):
#     user_input = request.GET.get('msg', '').strip()
    
#     # 1. Handle empty input immediately
#     if not user_input:
#         return JsonResponse({'response': "How can I help you today?"})

#     # 2. Let the Bot handle Intent, State, and Greetings
#     # bot.respond now handles identify_intent internally
#     response_text = bot.respond(user_input)

#     # 3. Only if the bot is completely lost, try the Database
#     if response_text == "FALLBACK_TO_DB":
#         db_row = None
#         try:
#             user_input_low = user_input.lower()
#             query_vector = embed_model.encode(user_input_low).tolist()
#             conn = get_db_connection()
#             cur = conn.cursor()
#             search_query = """
#                 SELECT answer, medicine FROM medical_knowledge 
#                 WHERE embedding <=> %s::vector < 0.50
#                 ORDER BY embedding <=> %s::vector LIMIT 1;
#             """
#             cur.execute(search_query, (query_vector, query_vector))
#             db_row = cur.fetchone()
#             cur.close()
#             conn.close()
#         except Exception as e:
#             print(f"Database Error: {e}")

#         if db_row:
#             answer, medicine = db_row
#             return JsonResponse({'response': f"For your symptoms, we suggest <b>{medicine}</b>. {answer}"})

#     # 4. Return the Bot's response (Greeting, Booking, or Symptom info)
#     return JsonResponse({'response': response_text})





# def chat_response(request):
#     user_input = request.GET.get('msg', '').strip()
#     user_input_low = user_input.lower()
    
#     if not user_input:
#         return JsonResponse({'response': "How can I help you today?"})

#     # 1. IDENTIFY INTENT
    
#     intent = bot.identify_intent(user_input_low)

#     # 2. PRIORITY 1: DIAGNOSTIC CHAINS & BOOKING & GREETINGS
    
#     if (intent is not None) or (bot.state != "START"):
#         response_text = bot.respond(user_input)
        
#         # We only exit this block and go to DB if the bot explicitly doesn't know what to do
#         if response_text != "FALLBACK_TO_DB":
#             return JsonResponse({'response': response_text})

#     # 3. PRIORITY 2: MEDICAL SYMPTOM SEARCH (Postgres)
    
#     db_row = None
#     try:
#         query_vector = embed_model.encode(user_input_low).tolist()
#         conn = get_db_connection()
#         cur = conn.cursor()
#         search_query = """
#             SELECT answer, medicine FROM medical_knowledge 
#             WHERE embedding <=> %s::vector < 0.50
#             ORDER BY embedding <=> %s::vector LIMIT 1;
#         """
#         cur.execute(search_query, (query_vector, query_vector))
#         db_row = cur.fetchone()
#         cur.close()
#         conn.close()
#     except Exception as e:
#         print(f"Database Error: {e}")

#     # 4. RESULT HANDLING FROM DATABASE
#     if db_row:
#         answer, medicine = db_row
#         return JsonResponse({'response': f"For your symptoms, we suggest <b>{medicine}</b>. {answer}"})

#     # 5. FINAL FALLBACK
#     return JsonResponse({'response': "I'm not quite sure. Would you like to **book an appointment** with a specialist?"})

#==============================chat_response() closes here==================

# FUNCTION 1: 
def chat_with_button(request):
    try:
        response = chat_response(request)
        data = json.loads(response.content)
        msg = data.get('response', '')

        # Use Regex to find the disease name inside <b> tags
        # import re
        # match = re.search(r'<b>(.*?)</b>', msg)

        # if match and ("may have" in msg or "complete" in msg):
        #     disease_name = match.group(1)

        if data.get('is_final') or "may have" in msg:
            import re
            match = re.search(r'<b>(.*?)</b>', msg)

            if match:
                disease_name = match.group(1).strip()
                precautions = data.get('precautions', [])
                
                # 1. Build Precaution HTML
                prec_html = ""
                if precautions:
                    prec_html = "<br><br><b>⚠️ Recommended Precautions:</b><ul class='precaution-list'>"
                    for p in precautions:
                        if str(p) != 'nan':
                            prec_html += f"<li>{p.strip().capitalize()}</li>"
                    prec_html += "</ul>"

                d_check = disease_name.lower()

                if any(x in d_check for x in ['dermatology', 'skin', 'rash', 'acne', 'fungal']):
                    doctor_name = "Dr. Chetan Raj"
                elif any(x in d_check for x in ['emergency', 'injury', 'accident']):
                    doctor_name = "Dr. Vikas Gupta"
                elif any(x in d_check for x in ['colon', 'rectal', 'digestive']):
                    doctor_name = "Dr. Janu Manu"
                elif any(x in d_check for x in ['anesthesia', 'surgery']):
                    doctor_name = "Dr. Amit Patel"
                else:
                    doctor_name = "Dr. Sunil Rajendran"

            

                url_name = disease_name.replace(" ", "%20")
                url_doc = doctor_name.replace(" ", "%20")

                button_html = (
                    f'<a href="/book-appointment/?symptom={url_name}&doctor_name={url_doc}" class="btn-book">'
                    f'📅 Book Appointment for {disease_name} with {doctor_name}'
                    f'</a>'
                )

                data['response'] = msg + prec_html + button_html
        
        return JsonResponse(data)
    
    except Exception as e:
        print(f"Error in chat_with_button: {e}")
        return JsonResponse({'response': "I encountered an error. Let's try again. What is your main symptom?"})
    


    

def book_appointment_view(request):
    now = datetime.now()
    doctor_name = request.GET.get('doctor_name')
    selected_date = request.GET.get('appointment_date')
    

    prefilled_symptom = request.GET.get('symptom', '')

    booked_slots = []
    if selected_date and doctor_name:
        # We query 'description' because that's where the time string is saved
        booked_slots = models.Appointment.objects.filter(
            doctorName=doctor_name, 
            appointmentDate__date=selected_date
        ).values_list('description', flat=True)

    context = {
        'symptom': prefilled_symptom,
        'doctor_name': doctor_name,
        'current_hour': now.hour,
        'current_minute': now.minute,
        'today': date.today(),  
        'booked_slots': list(booked_slots),
    }

    return render(request, 'hospital/appointment_form.html', context)

    # return render(request, 'hospital/appointment_form.html', {
    #     'symptom': prefilled_symptom
    # })






def check_slots(request):
    doctor_name = request.GET.get('doctor_name')
    date_str = request.GET.get('appointment_date')
    
    # 1. Get already booked slots from Database
    booked_descriptions = models.Appointment.objects.filter(
        doctorName=doctor_name, 
        appointmentDate__date=date_str,
        status=True
    ).values_list('description', flat=True)
    
    booked_list = list(booked_descriptions)

    # 2. Logic to hide past slots if the date is TODAY
    past_slots = []
    if date_str == str(datetime.now().date()):
        current_hour = datetime.now().hour
        
        # Define what hour each slot belongs to
        time_lookup = {
            "10:00 AM": 10, "11:00 AM": 11, "12:00 PM": 12,
            "02:00 PM": 14, "03:00 PM": 15, "04:00 PM": 16,
            "06:00 PM": 18, "07:00 PM": 19, "08:00 PM": 20,
        }
        
        for slot_name, hour in time_lookup.items():
            if hour <= current_hour:
                past_slots.append(slot_name)

    return JsonResponse({
        'booked_slots': booked_list,
        'past_slots': past_slots  
    })












# def chat_with_button(request):
#     # 1. Get the response from our Zero-Loop medical engine
#     response = chat_response(request)
#     data = json.loads(response.content)
#     msg = data.get('response', '')
    
#     # 2. Logic: If the user just types "yes" but a button is already on screen
#     user_input = request.GET.get('msg', '').strip().lower()
#     if user_input == "yes" and "Book Appointment" in msg:
#         data['response'] = "Please click the green button above to choose your preferred time slot. 🕒"
#         return JsonResponse(data)

#     # 3. DYNAMIC BUTTON ATTACHMENT
#     # If the message contains "Diagnosis complete" or "you may have", attach the button
#     if "Diagnosis complete" in msg or "you may have" in msg.lower():
        
#         # Extract the disease name from the message to use in the booking link
#         # We look for the text between <b> and </b> tags
#         import re
#         match = re.search(r'<b>(.*?)</b>', msg)
#         disease_name = match.group(1) if match else "Medical Issue"
        
#         # Clean the name for the URL
#         url_disease_name = disease_name.replace(" ", "%20")

#         button_html = (
#             f'<br><br><a href="/book-appointment/?symptom={url_disease_name}" '
#             f'style="display: inline-block; padding: 12px 20px; background-color: #28a745; '
#             f'color: white; text-decoration: none; border-radius: 6px; font-weight: bold; '
#             f'font-family: Arial, sans-serif; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">'
#             f'📅 Book Appointment for {disease_name}</a>'
#         )
        
#         data['response'] = msg + button_html

#     return JsonResponse(data)
    









#============================================================================


# ---- This is our Bridge function ----
# def call_chatbot_api(primary, follow_up):
    # url = "http://127.0.0.1:8000/diagnose" # This is Chatbot api address
    # url = "http://127.0.0.1:8001/diagnose"
    # payload = {"primary_symptom": primary, "follow_up_answer": follow_up}
    # try:
    #     response = requests.post(url, json=payload)
    #     return response.json()
    # except:
    #     return None

# ---- Our View that handles the chat page ----
# @login_required(login_url='patientlogin')

#==============================================================================
#==============================================================================
#========================chatbot_page starts here==============================
#==============================================================================
#==============================================================================



# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # 2. Get Input and Create Embedding
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}".strip()
#         request.session['temp_symptoms'] = user_query 

#         try:
#             query_vector = embed_model.encode(user_query).tolist()
#         except Exception as e:
#             print(f"Embedding Error: {e}")
#             query_vector = None

#         # 3. SEMANTIC SEARCH
#         db_row = None
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         try:
#             if query_vector:
#                 search_query = """
#                     SELECT question, answer, medicine 
#                     FROM medical_knowledge 
#                     ORDER BY embedding <=> %s::vector 
#                     LIMIT 1;
#                 """
#                 cur.execute(search_query, (query_vector,))
#                 db_row = cur.fetchone()
#             else:
#                 cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#                 db_row = cur.fetchone()
#         except Exception as e:
#             conn.rollback() 
#             cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#             db_row = cur.fetchone()
#         finally:
#             cur.close()
#             conn.close()

#         if db_row:
#             matched_q, answer, medicine = db_row
#             matched_q = matched_q.lower()
#             user_query_low = user_query.lower()
            
#             # 4. DYNAMIC DOCTOR LOGIC
#             if any(word in matched_q for word in ['stomach', 'acidity', 'rectal', 'gastric', 'digestion']):
#                 dept_to_find = "Colon and Rectal Surgeons"
#             elif any(word in matched_q for word in ['skin', 'rash', 'acne', 'dermatology']):
#                 dept_to_find = "Dermatologists"
#             elif any(word in matched_q for word in ['pain', 'back', 'neck', 'spine']):
#                 dept_to_find = "General"
#             elif any(word in matched_q for word in ['accident', 'emergency', 'broken', 'fracture']):
#                 dept_to_find = "Emergency Medicine Specialists"
#             else:
#                 dept_to_find = "General"

#             suggested_doctor = models.Doctor.objects.filter(
#                 department__icontains=dept_to_find,
#                 status=True
#             ).first()

#             # 5. UPDATED STATUS LOGIC (Handling chronic symptoms)
#             # Keywords that indicate a need for a formal appointment
#             chronic_keywords = ['week', 'month', 'years', 'long time', 'persistent', 'since']

#             if any(word in user_query_low for word in ['broken', 'bleed', 'emergency', 'accident', 'chest pain']):
#                 status = "emergency"
#             # If the user mentions a duration like "3 weeks", force Consultation
#             elif any(word in user_query_low for word in chronic_keywords):
#                 status = "consultation"
#             elif medicine and medicine.lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if (status == "normal") else "Requires Doctor Consultation",
#                 'advice': answer,
#                 'doctor_name': f"Dr. {suggested_doctor.user.first_name} ({suggested_doctor.department})" if suggested_doctor else "Dr. Sunil Rajendran (MBBS)",
#                 'name': patient_name
#             }
#         else:
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found. Please consult our staff.',
#                 'doctor_name': 'Dr. Sunil Rajendran MBBS'
#             }
    
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})

# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # 2. Get Input and Create Embedding
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}".strip()
#         request.session['temp_symptoms'] = user_query 

#         # Use the global embed_model
#         try:
#             query_vector = embed_model.encode(user_query).tolist()
#         except Exception as e:
#             print(f"Embedding Error: {e}")
#             query_vector = None

#         # 3. SEMANTIC SEARCH (Using existing columns only)
#         db_row = None
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         try:
#             if query_vector:
#                 # Search by semantic meaning
#                 search_query = """
#                     SELECT question, answer, medicine 
#                     FROM medical_knowledge 
#                     ORDER BY embedding <=> %s::vector 
#                     LIMIT 1;
#                 """
#                 cur.execute(search_query, (query_vector,))
#                 db_row = cur.fetchone()
#             else:
#                 # Fallback to basic text search if embedding fails
#                 cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#                 db_row = cur.fetchone()
#         except Exception as e:
#             conn.rollback() # CRITICAL: Clears the "InFailedSqlTransaction"
#             print(f"Semantic Search Failed: {e}")
#             # Final fallback
#             cur.execute('SELECT question, answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;', ('%' + primary + '%',))
#             db_row = cur.fetchone()
#         finally:
#             cur.close()
#             conn.close()

#         if db_row:
#             matched_q, answer, medicine = db_row
#             matched_q = matched_q.lower()
            
#             # 4. DYNAMIC DOCTOR LOGIC (Mapping to 'department')
#             # We map keywords from the matched question to your Doctor.department options
#             if any(word in matched_q for word in ['stomach', 'acidity', 'rectal', 'gastric', 'digestion']):
#                 dept_to_find = "Colon and Rectal Surgeons"
#             elif any(word in matched_q for word in ['skin', 'rash', 'acne', 'dermatology']):
#                 dept_to_find = "Dermatologists"
#             elif any(word in matched_q for word in ['pain', 'back', 'neck', 'spine']):
#                 dept_to_find = "Anesthesiologists"
#             elif any(word in matched_q for word in ['accident', 'emergency', 'broken', 'fracture']):
#                 dept_to_find = "Emergency Medicine Specialists"
#             else:
#                 dept_to_find = "General"

#             # Use only 'department' as your model doesn't have 'specialty'
#             suggested_doctor = models.Doctor.objects.filter(
#                 department__icontains=dept_to_find,
#                 status=True
#             ).first()

#             # 5. STATUS LOGIC
#             if any(word in user_query.lower() for word in ['broken', 'bleed', 'emergency', 'accident']):
#                 status = "emergency"
#             elif medicine and medicine.lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if medicine else "Consult Specialist",
#                 'advice': answer,
#                 'doctor_name': f"Dr. {suggested_doctor.user.first_name} ({suggested_doctor.department})" if suggested_doctor else "Dr. Sunil Rajendran (MBBS)",
#                 'name': patient_name
#             }
#         else:
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found in our database. Please consult our staff.',
#                 'doctor_name': 'Dr. Sunil Rajendran MBBS'
#             }
    
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})

# def chatbot_page(request):
#     result = None #original
#     if request.method == 'POST':
#         # 1. Capture Patient Info (Now capturing mobile too!)
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # 2. Get Input and store as symptoms
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}".strip()
        
#         # Save symptoms to session so confirm_appointment can grab it
#         request.session['temp_symptoms'] = user_query 

#         # 3. Query the medical_knowledge rows
#         conn = get_db_connection()
#         cur = conn.cursor()
#         query = 'SELECT answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;'
#         cur.execute(query, ('%' + primary + '%',))
#         db_row = cur.fetchone()
#         cur.close()
#         conn.close()

#         if db_row:
#             answer, medicine = db_row
#             if any(word in user_query.lower() for word in ['broken', 'bleed', 'accident', 'fracture', 'leg']):
#                 status = "emergency"
#             elif medicine and medicine.strip().lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if medicine else "Consult Specialist",
#                 'advice': answer,
#                 'doctor_name': "Dr. janu manu Colon and Rectal Surgeons" if status == "consultation" else None,
#                 'name': patient_name
#             }
#         else:
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found. Please consult our staff.',
#                 'doctor_name': 'Dr. sunil rajendran MBBS'
#             }

#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})

# def chatbot_page(request):
#     result = None     # for different doctors only
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile') 
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # 2. Get Input and store as symptoms
#         primary = request.POST.get('symptom1', '').lower()
#         follow_up = request.POST.get('symptom2', '').lower()
#         user_query = f"{primary} {follow_up}".strip()
#         request.session['temp_symptoms'] = user_query 

#         # 3. SMART TRIAGE LOGIC: Match symptoms to Doctor Specialties
#         # Default fallback is Dr. Sunil
#         suggested_doctor = "Dr. sunil rajendran MBBS" 
        
#         triage_map = {
#             'skin': "Dr. chetan raj Dermatologists",
#             'rash': "Dr. prakash raj Dermatologists",
#             'acne': "Dr. chetan raj Dermatologists",
#             'emergency': "Dr. vikas gupta Emergency Medicine Specialists",
#             'accident': "Dr. vikas gupta Emergency Medicine Specialists",
#             'fracture': "Dr. vikas gupta Emergency Medicine Specialists",
#             'pain': "Dr. amit patel Anesthesiologists",
#             'back pain': "Dr. Baghel Kadre Anesthesiologists",
#             'stomach': "Dr. janu manu Colon and Rectal Surgeons",
#             'digestion': "Dr. janu manu Colon and Rectal Surgeons",
#             'constipation': "Dr. janu manu Colon and Rectal Surgeons"
#         }

#         for keyword, doctor in triage_map.items():
#             if keyword in user_query:
#                 suggested_doctor = doctor
#                 break

#         # 4. Query the medical_knowledge rows
#         conn = get_db_connection()
#         cur = conn.cursor()
#         query = 'SELECT answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;'
#         cur.execute(query, ('%' + primary + '%',))
#         db_row = cur.fetchone()
#         cur.close()
#         conn.close()

#         if db_row:
#             answer, medicine = db_row
#             # Determine status
#             if any(word in user_query for word in ['broken', 'bleed', 'accident', 'fracture']):
#                 status = "emergency"
#             elif medicine and medicine.strip().lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if medicine else "Consult Specialist",
#                 'advice': answer,
#                 'doctor_name': suggested_doctor, # Dynamic doctor assignment
#                 'name': patient_name
#             }
#         else:
#             # Fallback when no medical advice found
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found in our database. I have assigned you to a specialist for review.',
#                 'doctor_name': suggested_doctor # Dynamic doctor assignment
#             }

#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})



# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info (Ensures Ronny, not Nehal)
#         patient_name = request.POST.get('name')
#         request.session['temp_name'] = patient_name
#         request.session.modified = True 

#         # 2. Get Input
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')
#         user_query = f"{primary} {follow_up}"

#         # 3. Query the 16,407 rows in medical_knowledge
#         conn = get_db_connection()
#         cur = conn.cursor()
        
#         # Using exact column names from your image: question, answer, medicine
#         # We use ILIKE for a case-insensitive search
#         query = 'SELECT answer, medicine FROM medical_knowledge WHERE question ILIKE %s LIMIT 1;'
        
#         cur.execute(query, ('%' + primary + '%',))
#         db_row = cur.fetchone()
        
#         cur.close()
#         conn.close()

#         if db_row:
#             # We only expect 2 values now: answer and medicine
#             answer, medicine = db_row
            
#             # DETERMINING STATUS FROM YOUR DATA
#             # 1. Check for Emergency Keywords in the user input
#             if any(word in user_query for word in ['broken', 'bleed', 'accident', 'fracture', 'leg']):
#                 status = "emergency"
#             # 2. If medicine is provided in the DB, it's a 'normal' case (e.g., Paracetamol)
#             elif medicine and medicine.strip().lower() != 'none' and medicine.strip() != '':
#                 status = "normal"
#             # 3. Otherwise, it's a Consultation
#             else:
#                 status = "consultation"

#             result = {
#                 'status': status,
#                 'medicine': medicine if medicine else "Consult Specialist",
#                 'advice': answer,
#                 'doctor_name': "Dr. janu manu Colon and Rectal Surgeons" if status == "consultation" else None,
#                 'name': patient_name
#             }
#         else:
#             # Fallback if no match is found in the 16k rows
#             result = {
#                 'status': 'consultation',
#                 'medicine': 'General Evaluation',
#                 'advice': 'No specific match found. Please consult our staff.',
#                 'doctor_name': 'Dr. sunil rajendran MBBS'
#             }

#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})


# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture and Force-Save Patient Info immediately
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile')
        
#         # This overwrites any old name (like Nehal) with the new one (like Ronny)
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile
#         request.session.modified = True 

#         # 2. Capture Symptoms
#         primary = request.POST.get('symptom1', '').strip()
#         follow_up = request.POST.get('symptom2', '').strip()
#         user_input_lower = (primary + " " + follow_up).lower()

#         # 3. Call AI Engine
#         result = call_chatbot_api(primary, follow_up)
        
#         if result:
#             # --- ZYDUS DYNAMIC DOCTOR ROUTING ---
#             is_intense_back = "back pain" in primary.lower() and \
#                               ("intense" in follow_up.lower() or "3 weeks" in follow_up.lower() or "today morning" in follow_up.lower())

#             if is_intense_back:
#                 ai_medicine = "🏥 Orthopedic Specialist Required"
#                 note = "Intense back pain detected. Specialist review recommended."
#                 status = "consultation" 
#                 result['doctor_name'] = "Dr. Janu Manu" 
            
#             elif "chest pain" in primary.lower() and ("racing" in follow_up.lower() or "3 weeks" in follow_up.lower()):
#                 ai_medicine = "⚠️ Cardiac Evaluation Required"
#                 note = "Priority Cardiac Triage."
#                 status = "consultation"
#                 result['doctor_name'] = "Dr. Manu" 
            
#             elif any(word in user_input_lower for word in ['broken', 'bleed', 'accident', 'leg']):
#                 ai_medicine = "🚨 EMERGENCY"
#                 note = "Severe trauma detected. Proceed to ER."
#                 status = "emergency"
            
#             else:
#                 ai_medicine = result.get('final_diagnosis') or 'General Consultation'
#                 note = 'Consult a doctor if symptoms persist.'
#                 status = "consultation"
#                 result['doctor_name'] = "Dr. Janu Manu"

#             # 4. Save to session
#             request.session['last_ai_prescription'] = {
#                 'medicine': ai_medicine, 
#                 'raw_symptoms': f"{primary}. {follow_up}".strip().capitalize(),
#                 'status': status,
#                 'date': datetime.datetime.now().strftime("%b %d, %Y"),
#                 'note': note
#             }
            
#             result['status'] = status
#             result['medicine'] = ai_medicine
#             result['advice'] = note
       
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})

# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile')
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile

#         # 2. Capture Symptoms
#         primary = request.POST.get('symptom1', '').strip()
#         follow_up = request.POST.get('symptom2', '').strip()
#         user_input_lower = (primary + " " + follow_up).lower()

#         # 3. Call AI Engine
#         result = call_chatbot_api(primary, follow_up)
        
#         if result:
#             # --- ZYDUS DYNAMIC DOCTOR ROUTING ---
            
#             # Check for "Back Pain" + "3 weeks" / "Intense"
#             is_intense_back = "back pain" in primary.lower() and \
#                               ("intense" in follow_up.lower() or "3 weeks" in follow_up.lower() or "today morning" in follow_up.lower())

#             if is_intense_back:
#                 ai_medicine = "🏥 Orthopedic Specialist Required"
#                 note = "Intense back pain detected. Specialist review recommended."
#                 status = "consultation" 
#                 result['doctor_name'] = "Dr. Janu Manu" # <--- Automatically Assigned
            
#             elif "chest pain" in primary.lower() and ("racing" in follow_up.lower() or "3 weeks" in follow_up.lower()):
#                 ai_medicine = "⚠️ Cardiac Evaluation Required"
#                 note = "Priority Cardiac Triage."
#                 status = "consultation"
#                 result['doctor_name'] = "Dr. Manu" 
            
#             elif "fever" in primary.lower() and "headache" in follow_up.lower():
#                 ai_medicine = "Paracetamol (500mg)"
#                 note = "General symptoms detected."
#                 status = "normal"
            
#             else:
#                 ai_medicine = result.get('final_diagnosis') or 'General Consultation'
#                 note = 'Consult a doctor if symptoms persist.'
#                 status = "consultation"
#                 result['doctor_name'] = "Dr. Janu Manu" # Default specialist

#             # 4. Save to session for the Doctor Dashboard
#             request.session['last_ai_prescription'] = {
#                 'medicine': ai_medicine, 
#                 'raw_symptoms': f"{primary}. {follow_up}".strip().capitalize(),
#                 'status': status,
#                 'date': datetime.datetime.now().strftime("%b %d, %Y"),
#                 'note': note
#             }
#             request.session.modified = True
            
#             result['status'] = status
#             result['medicine'] = ai_medicine
#             result['advice'] = note
       
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})

# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile')
        
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile

#         # 2. Capture Symptoms from Multi-Step Form
#         primary = request.POST.get('symptom1', '').strip()
#         follow_up = request.POST.get('symptom2', '').strip()
        
#         user_input_lower = (primary + " " + follow_up).lower()

#         # 3. Call AI Engine for Initial Diagnosis
#         result = call_chatbot_api(primary, follow_up)
        
#         if result:
#             # --- ZYDUS SMART TRIAGE LOGIC ---
            
#             # CASE A: IMMEDIATE PHYSICAL EMERGENCY (Trauma)
#             emergency_keywords = ['broken', 'bleed', 'accident', 'fracture', 'cut']
#             is_emergency = any(word in user_input_lower for word in emergency_keywords)

#             # CASE B: CRITICAL HEART EVALUATION
#             is_critical_heart = "chest pain" in primary.lower() and \
#                                 ("racing" in follow_up.lower() or "3 weeks" in follow_up.lower())

#             # CASE C: INTENSE BACK PAIN (Your New Requirement)
#             is_intense_back = "back pain" in primary.lower() and \
#                               ("intense" in follow_up.lower() or "3 weeks" in follow_up.lower())

#             if is_emergency:
#                 ai_medicine = "🚨 EMERGENCY: Trauma/Injury"
#                 details = "First Aid: Apply pressure. Do not move limb."
#                 note = "Critical Alert: Physical intervention required. Proceed to ER."
#                 status = "emergency"
            
#             elif is_critical_heart:
#                 ai_medicine = "⚠️ CRITICAL: Cardiac Evaluation Required"
#                 details = "Patient reports persistent chest pain with racing heart/duration."
#                 note = "IMMEDIATE BOOKING: High Priority Cardiac Triage."
#                 status = "consultation" 
#                 result['doctor_name'] = "Dr. Cardiologist" 

#             elif is_intense_back:
#                 ai_medicine = "🏥 SPECIALIST: Orthopedic Evaluation Needed"
#                 details = "Intense/Chronic back pain detected. Specialist review required for spinal health."
#                 note = "Persistent pain for 3 weeks requires clinical assessment."
#                 status = "consultation" # This triggers the Book Appointment Button
#                 result['doctor_name'] = "Dr. Orthopedic Specialist"

#             # CASE D: NORMAL SYMPTOMS (e.g. Fever + Headache)
#             elif "fever" in primary.lower() and "headache" in follow_up.lower():
#                 ai_medicine = "Paracetamol (500mg)"
#                 details = "Standard viral management. Stay hydrated and rest."
#                 note = "General symptoms detected. Medicine name provided."
#                 status = "normal" # Shows medicine name, NOT booking button
            
#             else:
#                 ai_medicine = result.get('final_diagnosis') or result.get('diagnosis') or 'General Consultation'
#                 details = result.get('treatment_suggestion', 'Please consult a doctor.')
#                 note = 'Consult a doctor if symptoms persist.'
#                 status = "consultation"
#                 result['doctor_name'] = "General Physician"

#             # 4. Save structured data to session for the Doctor Dashboard
#             request.session['last_ai_prescription'] = {
#                 'medicine': ai_medicine, 
#                 'raw_symptoms': f"{primary}. {follow_up}".strip().capitalize(),
#                 'details': details,
#                 'status': status,
#                 'date': datetime.datetime.now().strftime("%b %d, %Y"),
#                 'note': note
#             }
#             request.session.modified = True
            
#             # Update the result object for the HTML template
#             result['status'] = status
#             result['medicine'] = ai_medicine
#             result['advice'] = note
       
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})



# def chatbot_page(request):
#     result = None
#     if request.method == 'POST':
#         # 1. Capture Patient Info
#         patient_name = request.POST.get('name')
#         patient_mobile = request.POST.get('mobile')
        
#         # Save to session immediately
#         request.session['temp_name'] = patient_name
#         request.session['temp_mobile'] = patient_mobile

#         # 2. Capture Symptoms for AI
#         primary = request.POST.get('symptom1', '')
#         follow_up = request.POST.get('symptom2', '')

        
        
#         # 3. Call the AI Engine
#         result = call_chatbot_api(primary, follow_up)
        
#         if result:
#             # --- SMART TRIAGE LOGIC ---
#             user_input = (primary + " " + follow_up).strip()
#             user_input_lower = user_input.lower()
            
#             emergency_keywords = ['broken', 'bleed', 'accident', 'fracture', 'chest pain', 'breath', 'cut']
#             is_emergency = any(word in user_input_lower for word in emergency_keywords)

#             if is_emergency:
#                 ai_medicine = "🚨 EMERGENCY: Trauma/Injury"
#                 details = "First Aid: Apply pressure. Do not move limb."
#                 schedule = "EMERGENCY: HEAD TO ZYDUS HOSPITAL"
#                 note = "Critical Alert: Physical intervention required."
#             else:
#                 ai_medicine = result.get('final_diagnosis') or result.get('diagnosis') or 'General Consultation'
#                 details = result.get('treatment_suggestion', 'Please consult a doctor.')
#                 schedule = 'Morning & Evening (After Food)'
#                 note = 'Consult a doctor if symptoms persist.'

#             # 4. Save structured data to session
#             # We add 'raw_symptoms' so the doctor sees the actual complaint
#             request.session['last_ai_prescription'] = {
#                 'medicine': ai_medicine, 
#                 'raw_symptoms': user_input if user_input else "General Consultation",
#                 'details': details,
#                 'schedule': schedule,
#                 'date': datetime.datetime.now().strftime("%b %d, %Y"),
#                 'note': note
#             }
#             # Ensure session is saved
#             request.session.modified = True
       
#     return render(request, 'hospital/chatbot_standalone.html', {'result': result})


#==============================================================================
#==============================================================================
#=======================chatbot_page ends here=================================
#==============================================================================
#==============================================================================





def guest_treatment_profile(request):
    # Retrieve the AI data we just saved in the chatbot_page session
    prescription = request.session.get('last_ai_prescription')
    patient_name = request.session.get('temp_name', 'Guest Patient')

    if not prescription:
        # If the user goes here without using the chatbot first
        return render(request, 'hospital/guest_profile_empty.html')

    return render(request, 'hospital/guest_profile.html', {
        'data': prescription,
        'patient_name': patient_name
    })



#------------------------ PATIENT RELATED VIEWS END ------------------------------
#---------------------------------------------------------------------------------








#---------------------------------------------------------------------------------
#------------------------ ABOUT US AND CONTACT US VIEWS START ------------------------------
#---------------------------------------------------------------------------------
def aboutus_view(request):
    return render(request,'hospital/aboutus.html')

def contactus_view(request):
    sub = forms.ContactusForm()
    if request.method == 'POST':
        sub = forms.ContactusForm(request.POST)
        if sub.is_valid():
            email = sub.cleaned_data['Email']
            name=sub.cleaned_data['Name']
            message = sub.cleaned_data['Message']
            send_mail(str(name)+' || '+str(email),message,settings.EMAIL_HOST_USER, settings.EMAIL_RECEIVING_USER, fail_silently = False)
            return render(request, 'hospital/contactussuccess.html')
    return render(request, 'hospital/contactus.html', {'form':sub})


#---------------------------------------------------------------------------------
#------------------------ ADMIN RELATED VIEWS END ------------------------------
#---------------------------------------------------------------------------------




