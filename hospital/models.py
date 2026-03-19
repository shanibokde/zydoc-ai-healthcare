from django.db import models
from django.contrib.auth.models import User



departments=[('Cardiologist','Cardiologist'),
('Dermatologists','Dermatologists'),
('Emergency Medicine Specialists','Emergency Medicine Specialists'),
('Allergists/Immunologists','Allergists/Immunologists'),
('Anesthesiologists','Anesthesiologists'),
('MBBS','MBBS'),
('Colon and Rectal Surgeons','Colon and Rectal Surgeons')
]
class Doctor(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    profile_pic= models.ImageField(upload_to='profile_pic/DoctorProfilePic/',null=True,blank=True)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=True)
    department= models.CharField(max_length=50,choices=departments,default='Cardiologist')
    status=models.BooleanField(default=False)
    @property
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def get_photo_url(self):
        if self.profile_pic and hasattr(self.profile_pic, 'url'):
            try:
                return self.profile_pic.url
            except ValueError:
                return "/static/images/default_user.png"
        
        return "/static/images/default_user.png"
    @property
    def get_id(self):
        return self.user.id
    def __str__(self):
        return "{} ({})".format(self.user.first_name,self.department)



class Patient(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    profile_pic= models.ImageField(upload_to='profile_pic/Patient/',null=True,blank=True)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=False)
    symptoms = models.CharField(max_length=100,null=False)
    assignedDoctorId = models.PositiveIntegerField(null=True)
    admitDate=models.DateField(auto_now=True)
    status=models.BooleanField(default=False)
    @property
    def get_name(self):
        return self.user.first_name+" "+self.user.last_name
    @property
    def profile_pic_url(self):
        if self.profile_pic and hasattr(self.profile_pic, 'url'):
            return self.profile_pic.url
        return '/static/images/default_avatar.png'
    @property
    def get_id(self):
        return self.user.id
    def __str__(self):
        return self.user.first_name+" ("+self.symptoms+")"
    
class LabReport(models.Model):
    REPORT_TYPES = [
        ('Blood Test', 'Blood Test'),
        ('X-Ray', 'X-Ray'),
        ('MRI', 'MRI'),
        ('Urine Test', 'Urine Test'),
        ('Other', 'Other'),
    ]
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    report_file = models.FileField(upload_to='lab_reports/')
    uploaded_date = models.DateTimeField(auto_now_add=True)
    doctor_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.report_type} for {self.patient.get_name}"
    
# class PatientHistory(models.Model):
#     patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
#     doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
#     visit_date = models.DateField(auto_now_add=True)
#     symptoms = models.TextField()
#     diagnosis = models.TextField()
#     prescription = models.TextField()

#     def __str__(self):
#         return f"{self.patient.get_name} - {self.visit_date}"


class Appointment(models.Model):
    patientId=models.PositiveIntegerField(null=True)
    doctorId=models.PositiveIntegerField(null=True)
    patientName=models.CharField(max_length=40,null=True)
    doctorName=models.CharField(max_length=40,null=True)
    appointmentDate = models.DateTimeField(null=True, blank=True)
    description=models.TextField(max_length=500)
    mobile = models.CharField(max_length=20, null=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    status=models.BooleanField(default=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doctorName', 'appointmentDate', 'description'], 
                name='unique_appointment'
            )
        ]


class Prescription(models.Model):
    patientId=models.PositiveIntegerField(null=True)
    patientName=models.CharField(max_length=40, null=True)
    doctorId=models.PositiveIntegerField(null=True)
    doctorName=models.CharField(max_length=40, null=True)
    consultationDate=models.DateField(auto_now_add=True, null=True)
    prescribeDate = models.DateField(auto_now_add=True)
    symptoms=models.CharField(max_length=100, null=True)
    medicine = models.CharField(max_length=100, null=True) 
    extra_notes = models.TextField(max_length=500, null=True)
    # medicine=models.TextField(max_length=500)
    # extra_notes=models.TextField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.patientName} - {self.consultationDate}"

class PrescriptionHistory(models.Model):
    patientId = models.PositiveIntegerField(null=True)
    patientName = models.CharField(max_length=40, null=True)
    doctorId = models.PositiveIntegerField(null=True)
    doctorName = models.CharField(max_length=40, null=True)
    symptoms = models.CharField(max_length=100, null=True)
    medicineName = models.CharField(max_length=100, null=True)
    prescribeDate = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.patientName} - {self.medicineName}"

class PatientDischargeDetails(models.Model):
    patientId=models.PositiveIntegerField(null=True)
    patientName=models.CharField(max_length=40)
    assignedDoctorName=models.CharField(max_length=40)
    address = models.CharField(max_length=40)
    mobile = models.CharField(max_length=20,null=True)
    symptoms = models.CharField(max_length=100,null=True)

    admitDate=models.DateField(null=False)
    releaseDate=models.DateField(null=False)
    daySpent=models.PositiveIntegerField(null=False)

    roomCharge=models.PositiveIntegerField(null=False)
    medicineCost=models.PositiveIntegerField(null=False)
    doctorFee=models.PositiveIntegerField(null=False)
    OtherCharge=models.PositiveIntegerField(null=False)
    total=models.PositiveIntegerField(null=False)


