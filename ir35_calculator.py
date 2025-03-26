import streamlit as st
from PIL import Image
from fpdf import FPDF
import matplotlib.pyplot as plt
import numpy as np
import os
from io import BytesIO

# Initialize session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'compare_mode' not in st.session_state:
    st.session_state.compare_mode = False

def ir35_tax_calculator(day_rate, work_days_per_year=220, pension_contribution_percent=0, 
                       employer_pension_percent=0, student_loan_plan="None", margin_percent=0, 
                       status="Inside IR35", vat_registered=False):
    """Calculate take-home pay for consultants inside or outside IR35."""
    
    # Constants
    annual_income = day_rate * work_days_per_year
    
    # VAT Calculation (only outside IR35)
    if status == "Outside IR35" and vat_registered:
        vat_amount = annual_income * 0.2
    else:
        vat_amount = 0
    
    margin = annual_income * (margin_percent / 100)
    annual_income -= margin  # Deduct company margin
    
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
    
    # Employer NI (only applies inside IR35)
    employer_ni_rate = 0.133
    inside_ir35 = status == "Inside IR35"
    employer_ni = (annual_income - ni_threshold) * employer_ni_rate if annual_income > ni_threshold and inside_ir35 else 0
    annual_income -= employer_ni  # Deduct Employer NI before tax
    
    # Pension Contributions
    employee_pension = annual_income * (pension_contribution_percent / 100)
    employer_pension = annual_income * (employer_pension_percent / 100)
    annual_income -= employee_pension
    
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
        "Gross Income": annual_income + employer_ni + employee_pension + margin,
        "Company Margin Deducted": margin,
        "Employer NI Deducted": employer_ni,
        "Employee Pension": employee_pension,
        "Employer Pension": employer_pension,
        "Income Tax": income_tax,
        "Employee NI": ni_contribution,
        "Student Loan Repayment": student_loan_repayment,
        "Net Take-Home Pay": take_home_pay,
        "VAT Amount": vat_amount
    }

def create_pie_chart(results):
    """Create a smaller pie chart and save to temporary file"""
    labels = ["Net Pay", "Income Tax", "NI", "Student Loan", "Pension"]
    values = [
        results["Net Take-Home Pay"],
        results["Income Tax"],
        results["Employee NI"],
        results["Student Loan Repayment"],
        results["Employee Pension"]
    ]
    
    fig, ax = plt.subplots(figsize=(3, 3))  # 50% smaller
    ax.pie(values, labels=labels, autopct='%1.1f%%', textprops={'fontsize': 6})
    plt.tight_layout()
    
    # Save to temporary file
    temp_file = "temp_pie_chart.png"
    plt.savefig(temp_file, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    return temp_file

def generate_pdf(result, include_tax=True, include_ni=True, include_pension=True, include_vat=True):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header with logo and tagline - more compact layout
    try:
        pdf.image("B2e Logo.png", 10, 8, 25)  # Smaller logo
    except:
        pass
    
    # Tagline in top right - smaller and tighter
    pdf.set_xy(120, 10)
    pdf.set_font("Arial", style='I', size=8)
    pdf.cell(80, 4, "Fuelling Transformation. Powered by Experts.", align='R')
    
    # Main title - less spacing
    pdf.set_font("Arial", size=12, style='B')  # Smaller title
    pdf.ln(15)  # Reduced spacing
    pdf.cell(200, 8, "IR35 Tax Calculation Results", ln=True, align='C')
    pdf.ln(5)  # Reduced spacing
    
    # Add pie chart - smaller and positioned better
    pie_chart_file = create_pie_chart(result)
    pdf.image(pie_chart_file, x=65, w=80)  # Centered and slightly larger
    if os.path.exists(pie_chart_file):
        os.remove(pie_chart_file)
    
    # Results section - tighter layout
    pdf.set_font("Arial", size=10)  # Smaller font
    pdf.ln(5)  # Reduced spacing
    
    # Key metrics first
    pdf.cell(100, 6, f"Gross Income: £{result['Gross Income']:,.2f}", ln=True)
    pdf.cell(100, 6, f"Net Take-Home Pay: £{result['Net Take-Home Pay']:,.2f}", ln=True)
    pdf.ln(3)
    
    # Detailed breakdown - two columns to save space
    col_width = 90
    pdf.set_font("Arial", size=9)
    
    if include_tax:
        pdf.cell(col_width, 5, f"Income Tax: £{result['Income Tax']:,.2f}")
    if include_ni:
        pdf.cell(col_width, 5, f"Employee NI: £{result['Employee NI']:,.2f}", ln=True)
        if result['Employer NI Deducted'] > 0:
            pdf.cell(col_width, 5, f"Employer NI: £{result['Employer NI Deducted']:,.2f}")
    
    if include_pension:
        pdf.cell(col_width, 5, f"Employee Pension: £{result['Employee Pension']:,.2f}", ln=True)
        if result['Employer Pension'] > 0:
            pdf.cell(col_width, 5, f"Employer Pension: £{result['Employer Pension']:,.2f}")
    
    if include_vat and result['VAT Amount'] > 0:
        pdf.cell(col_width, 5, f"VAT Amount: £{result['VAT Amount']:,.2f}", ln=True)
    
    # Footer with company details - much more compact
    pdf.set_y(-15)  # Higher up on the page
    pdf.set_font("Arial", size=6)  # Very small font
    pdf.set_text_color(100, 100, 100)
    
    # Single line for all footer info
    pdf.cell(200, 3, "Winchester House, 19 Bedford Row, London | VAT: 835 7085 10 | Company: 05008568 | ", align='C')
    
    # Website as clickable link
    pdf.set_text_color(0, 0, 255)
    pdf.cell(10, 3, "www.B2eConsulting.com", link="https://www.B2eConsulting.com", align='C')
    
    return pdf.output(dest='S').encode('latin1')

# Streamlit App Configuration
st.set_page_config(page_title="IR35 Tax Calculator", layout="wide")

# Add company logo
try:
    logo = Image.open("B2e Logo.png")
    st.image(logo, width=200)
except:
    st.write("")  # Skip if logo not found

st.title("IR35 Tax Calculator")

# Progress Bar
completion = 0
progress_bar = st.progress(0)

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        day_rate = st.number_input(
            "Enter your daily rate (£):", 
            min_value=0, 
            value=500,
            key="day_rate",
            help="Your daily contract rate before deductions"
        )
        work_days_per_year = st.number_input(
            "Enter workdays per year:", 
            min_value=1, 
            max_value=365, 
            value=220,
            key="work_days",
            help="Typically 220 days accounting for holidays and weekends"
        )
        pension_contribution_percent = st.number_input(
            "Employee Pension Contribution (%):", 
            min_value=0, 
            value=0,
            key="pension_contribution",
            help="Percentage of salary going to your pension"
        )
        employer_pension_percent = st.number_input(
            "Employer Pension Contribution (%):", 
            min_value=0, 
            value=3,
            key="employer_pension",
            help="Standard UK employer contribution is 3%+"
        )
        
    with col2:
        student_loan_plan = st.selectbox(
            "Student Loan Plan:", 
            ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
            key="student_loan",
            help="Select your student loan repayment plan"
        )
        margin_percent = st.number_input(
            "Company Margin Deduction (%):", 
            min_value=0, 
            value=10,
            key="margin_percent",
            help="Percentage kept by your umbrella company or agency"
        )
        status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            index=0,
            key="status",
            help="Inside: Treated as employee. Outside: Self-employed"
        )
        if status == "Outside IR35":
            vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=False,
                key="vat_registered",
                help="Check if you're VAT registered (outside IR35 only)"
            )
        else:
            vat_registered = False
    
    # Update progress based on inputs
    completion = 0
    if day_rate > 0: completion += 20
    if work_days_per_year > 0: completion += 20
    if pension_contribution_percent > 0: completion += 10
    if employer_pension_percent > 0: completion += 10
    if student_loan_plan != "None": completion += 10
    if margin_percent > 0: completion += 10
    if status: completion += 20
    progress_bar.progress(min(completion, 100))
    
    # Submit button for the form
    submitted = st.form_submit_button("Calculate")
    
    if submitted:
        st.session_state.results = ir35_tax_calculator(
            day_rate, work_days_per_year, pension_contribution_percent,
            employer_pension_percent, student_loan_plan, margin_percent, 
            status, vat_registered
        )

# Results Display
if st.session_state.results:
    st.subheader("Results")
    
    # Key Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gross Income", f"£{st.session_state.results['Gross Income']:,.2f}")
    with col2:
        st.metric("Total Deductions", f"£{sum([st.session_state.results['Income Tax'], st.session_state.results['Employee NI'], st.session_state.results['Student Loan Repayment']]):,.2f}")
    with col3:
        st.metric("Net Take-Home Pay", f"£{st.session_state.results['Net Take-Home Pay']:,.2f}")
    
    # Detailed Breakdown (always visible)
    st.subheader("Detailed Breakdown")
    for key, value in st.session_state.results.items():
        if key not in ["VAT Amount"] or (key == "VAT Amount" and value > 0):
            st.write(f"**{key}:** £{value:,.2f}")
    
    # Charts in tabs
    tab1, tab2 = st.tabs(["Pie Chart", "Bar Chart"])
    
    with tab1:
        # Smaller pie chart
        fig, ax = plt.subplots(figsize=(3, 3))  # 50% smaller
        labels = ["Net Pay", "Income Tax", "NI", "Student Loan", "Pension"]
        values = [
            st.session_state.results["Net Take-Home Pay"],
            st.session_state.results["Income Tax"],
            st.session_state.results["Employee NI"],
            st.session_state.results["Student Loan Repayment"],
            st.session_state.results["Employee Pension"]
        ]
        ax.pie(values, labels=labels, autopct='%1.1f%%', textprops={'fontsize': 6})
        st.pyplot(fig)
    
    with tab2:
        breakdown_data = {
            "Category": ["Tax", "NI", "Student Loan", "Pension", "Net Pay"],
            "Amount": [
                st.session_state.results["Income Tax"],
                st.session_state.results["Employee NI"],
                st.session_state.results["Student Loan Repayment"],
                st.session_state.results["Employee Pension"],
                st.session_state.results["Net Take-Home Pay"]
            ]
        }
        st.bar_chart(breakdown_data, x="Category", y="Amount")

# Comparison Mode
st.subheader("Comparison Mode")
compare = st.checkbox("Enable Comparison Mode")

if compare:
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Scenario 1**")
        day_rate1 = st.number_input("Daily Rate (£)", key="day_rate1", value=500)
        status1 = st.radio("IR35 Status", ["Inside IR35", "Outside IR35"], key="status1")
    
    with col2:
        st.write("**Scenario 2**")
        day_rate2 = st.number_input("Daily Rate (£)", key="day_rate2", value=600)
        status2 = st.radio("IR35 Status", ["Inside IR35", "Outside IR35"], key="status2")
    
    if st.button("Compare Scenarios"):
        result1 = ir35_tax_calculator(
            day_rate1, work_days_per_year, pension_contribution_percent,
            employer_pension_percent, student_loan_plan, margin_percent, status1
        )
        result2 = ir35_tax_calculator(
            day_rate2, work_days_per_year, pension_contribution_percent,
            employer_pension_percent, student_loan_plan, margin_percent, status2
        )
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Scenario 1")
            st.metric("Net Pay", f"£{result1['Net Take-Home Pay']:,.2f}")
        
        with col2:
            st.write("### Scenario 2")
            st.metric("Net Pay", f"£{result2['Net Take-Home Pay']:,.2f}")
        
        # Comparison chart
        compare_data = {
            "Scenario": ["1", "2"],
            "Net Pay": [result1['Net Take-Home Pay'], result2['Net Take-Home Pay']]
        }
        st.bar_chart(compare_data, x="Scenario", y="Net Pay")

# PDF Report Generation
st.subheader("Report Options")
include_tax = st.checkbox("Include Income Tax in PDF", value=True)
include_ni = st.checkbox("Include NI in PDF", value=True)
include_pension = st.checkbox("Include Pension in PDF", value=True)
include_vat = st.checkbox("Include VAT in PDF", value=True)

if st.session_state.results and st.button("Generate PDF Report"):
    pdf_data = generate_pdf(
        st.session_state.results,
        include_tax=include_tax,
        include_ni=include_ni,
        include_pension=include_pension,
        include_vat=include_vat
    )
    st.download_button(
        "Download Full Report",
        data=pdf_data,
        file_name="IR35_Tax_Report.pdf",
        mime="application/pdf"
    )
