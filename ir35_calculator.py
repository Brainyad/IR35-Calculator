import streamlit as st
from PIL import Image
import requests
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def ir35_tax_calculator(day_rate, work_days_per_year=220, pension_contribution_percent=0, student_loan_plan="None"):
    """Calculate take-home pay for consultants inside IR35."""
    
    # Constants
    annual_income = day_rate * work_days_per_year
    personal_allowance = 12570  # Tax-free allowance (2024/25)
    basic_rate_threshold = 50270
    higher_rate_threshold = 125140
    
    # Tax bands
    basic_rate = 0.2
    higher_rate = 0.4
    additional_rate = 0.45
    
    # National Insurance (NI)
    ni_threshold = 12570
    ni_lower = 0.08  # 8% for earnings above £12,570
    ni_upper = 0.02  # 2% for earnings above £50,270
    
    # Employer NI (deducted at source)
    employer_ni_rate = 0.133
    employer_ni = (annual_income - ni_threshold) * employer_ni_rate if annual_income > ni_threshold else 0
    annual_income -= employer_ni  # Deduct Employer NI before tax
    
    # Pension Contributions
    pension_contribution = annual_income * (pension_contribution_percent / 100)
    annual_income -= pension_contribution
    
    # Income Tax Calculation
    if annual_income <= personal_allowance:
        income_tax = 0
    elif annual_income <= basic_rate_threshold:
        income_tax = (annual_income - personal_allowance) * basic_rate
    elif annual_income <= higher_rate_threshold:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((annual_income - basic_rate_threshold) * higher_rate)
    else:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((higher_rate_threshold - basic_rate_threshold) * higher_rate) + ((annual_income - higher_rate_threshold) * additional_rate)
    
    # National Insurance (NI) Calculation
    if annual_income <= ni_threshold:
        ni_contribution = 0
    elif annual_income <= basic_rate_threshold:
        ni_contribution = (annual_income - ni_threshold) * ni_lower
    else:
        ni_contribution = ((basic_rate_threshold - ni_threshold) * ni_lower) + ((annual_income - basic_rate_threshold) * ni_upper)
    
    # Student Loan Calculation
    student_loan_repayment = 0
    if student_loan_plan == "Plan 1" and annual_income > 22015:
        student_loan_repayment = (annual_income - 22015) * 0.09
    elif student_loan_plan == "Plan 2" and annual_income > 27295:
        student_loan_repayment = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Plan 4" and annual_income > 31395:
        student_loan_repayment = (annual_income - 31395) * 0.09
    elif student_loan_plan == "Plan 5" and annual_income > 27295:
        student_loan_repayment = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Postgraduate Loan" and annual_income > 21000:
        student_loan_repayment = (annual_income - 21000) * 0.06
    
    # Final Take-Home Pay Calculation
    take_home_pay = annual_income - (income_tax + ni_contribution + student_loan_repayment)
    
    return {
        "Gross Income": annual_income + employer_ni + pension_contribution,
        "Employer NI Deducted": employer_ni,
        "Pension Contributions": pension_contribution,
        "Income Tax": income_tax,
        "Employee NI": ni_contribution,
        "Student Loan Repayment": student_loan_repayment,
        "Net Take-Home Pay": take_home_pay
    }

# Streamlit Web App
st.set_page_config(page_title="IR35 Tax Calculator", layout="wide")

# Company Logo
logo_url = "https://www.b2econsulting.com/wp-content/uploads/2017/07/B2E-Circle-for-flipboxes.png"
try:
    response = requests.get(logo_url)
    logo_image = Image.open(BytesIO(response.content))
    st.image(logo_image, width=150)
except Exception:
    st.write("**B2E Consulting**")

st.title("IR35 Tax Calculator")

# User Input
col1, col2 = st.columns(2)

with col1:
    day_rate = st.number_input("Enter your daily rate (£):", min_value=0, value=500)
    work_days_per_year = st.number_input("Enter workdays per year:", min_value=1, max_value=365, value=220)
    pension_contribution_percent = st.number_input("Pension Contribution (%):", min_value=0, value=0)

with col2:
    student_loan_plan = st.selectbox("Student Loan Plan:", ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"])

if st.button("Calculate"):
    result = ir35_tax_calculator(day_rate, work_days_per_year, pension_contribution_percent, student_loan_plan)
    
    st.subheader("Results")
    st.write(f"**Gross Income:** £{result['Gross Income']:,.2f}")
    st.write(f"**Employer NI Deducted:** £{result['Employer NI Deducted']:,.2f}")
    st.write(f"**Pension Contributions:** £{result['Pension Contributions']:,.2f}")
    st.write(f"**Income Tax:** £{result['Income Tax']:,.2f}")
    st.write(f"**Employee NI:** £{result['Employee NI']:,.2f}")
    st.write(f"**Student Loan Repayment:** £{result['Student Loan Repayment']:,.2f}")
    st.write(f"**Net Take-Home Pay:** £{result['Net Take-Home Pay']:,.2f}")