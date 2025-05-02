import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import math

# Initialize session state with proper default values
def init_session_state():
    session_vars = {
        'results': None,
        'compare_mode': False,
        'calculation_mode': "Client Rate",
        'status': "Inside IR35",
        'working_days': 0,
        'employer_pension_percent': 3.0,  # Added with default value
        'employee_pension': 5.0,
        'student_loan': "None",
        'days_per_week': 5,
        'start_date': datetime.today().date(),
        'end_date': (datetime.today() + timedelta(days=180)).date(),
        'vat_registered': False
    }
    
    for key, value in session_vars.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# UK Bank Holidays API
def get_uk_bank_holidays():
    try:
        response = requests.get('https://www.gov.uk/bank-holidays.json')
        data = response.json()
        england_holidays = data['england-and-wales']['events']
        return [datetime.strptime(event['date'], '%Y-%m-%d').date() for event in england_holidays]
    except:
        # Fallback to 2023 holidays if API fails
        return [
            datetime(2023, 1, 2).date(), datetime(2023, 4, 7).date(), 
            datetime(2023, 4, 10).date(), datetime(2023, 5, 1).date(),
            datetime(2023, 5, 8).date(), datetime(2023, 5, 29).date(),
            datetime(2023, 8, 28).date(), datetime(2023, 12, 25).date(),
            datetime(2023, 12, 26).date()
        ]

def calculate_working_days(start_date, end_date, days_per_week, bank_holidays):
    if start_date >= end_date:
        return 0
    total_days = (end_date - start_date).days + 1
    working_days = 0
    
    for day in range(total_days):
        current_date = start_date + timedelta(days=day)
        if current_date.weekday() < 5 and current_date not in bank_holidays:
            working_days += 1
    
    # Adjust for partial weeks based on days_per_week
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    adjusted_working_days = (full_weeks * days_per_week) + min(remaining_days, days_per_week)
    
    return adjusted_working_days

def calculate_holiday_components(pay_rate):
    """Calculate Basic Daily Rate and Holiday Pay from Pay Rate"""
    basic_daily_rate = pay_rate / (1 + 0.1454)  # 14.54% holiday pay
    holiday_pay = pay_rate - basic_daily_rate
    return round(basic_daily_rate), round(holiday_pay)

def calculate_base_rate(client_rate, margin_percent):
    """Calculate Base Rate from Client Rate and margin"""
    return client_rate * (1 - margin_percent/100)

def calculate_client_rate(base_rate, margin_percent):
    """Calculate Client Rate from Base Rate and margin"""
    return base_rate / (1 - margin_percent/100)

def calculate_pay_rate(base_rate):
    """Calculate Pay Rate from Base Rate with employer deductions (Inside IR35)"""
    # Total employer deductions = 15% NI + 3% Pension + 0.5% Levy = 18.5%
    return base_rate / 1.185

def calculate_base_rate_from_pay(pay_rate):
    """Calculate Base Rate from Pay Rate (Inside IR35)"""
    return pay_rate * 1.185

def calculate_employer_deductions(base_rate, working_days):
    """Calculate employer NI, pension, and levy amounts (daily and total)"""
    daily_ni = base_rate * 0.15
    daily_pension = base_rate * 0.03
    daily_levy = base_rate * 0.005
    total_ni = daily_ni * working_days
    total_pension = daily_pension * working_days
    total_levy = daily_levy * working_days
    
    return {
        "Daily Employer NI": round(daily_ni),
        "Daily Employer Pension": round(daily_pension),
        "Daily Apprentice Levy": round(daily_levy),
        "Total Employer NI": round(total_ni),
        "Total Employer Pension": round(total_pension),
        "Total Apprentice Levy": round(total_levy),
        "Total Employer Deductions": round((daily_ni + daily_pension + daily_levy) * working_days)
    }

def calculate_margin(client_rate, base_rate, working_days):
    """Calculate margin amounts (daily and total)"""
    daily_margin = client_rate - base_rate
    total_margin = daily_margin * working_days
    margin_percent = ((client_rate - base_rate) / client_rate) * 100
    
    return {
        "Daily Margin": round(daily_margin),
        "Total Margin": round(total_margin),
        "Margin Percentage": round(margin_percent, 1)
    }

def ir35_tax_calculator(pay_rate, working_days, pension_contribution_percent=5, 
                       student_loan_plan="None", status="Inside IR35", vat_registered=False):
    """Calculate take-home pay with proper IR35 status handling"""
    if status == "Outside IR35":
        # Simplified for Outside IR35 - no tax calculations
        annual_income = pay_rate * working_days
        vat_amount = annual_income * 0.2 if vat_registered else 0
        
        return {
            "Base Rate": pay_rate,
            "Pay Rate": pay_rate,
            "VAT Amount": round(vat_amount),
            "Working Days": working_days,
            "Project Total": round(annual_income),
            "Daily Rate": pay_rate,
            "Disclaimer": "As a self-employed consultant, you are responsible for calculating and paying your own taxes and National Insurance via Self Assessment. These figures show gross amounts only."
        }
    else:
        # Inside IR35 calculations
        annual_income = pay_rate * working_days
        personal_allowance = 12570
        basic_rate_threshold = 50270
        higher_rate_threshold = 125140
        
        # Tax bands
        basic_rate = 0.2
        higher_rate = 0.4
        additional_rate = 0.45
        
        # National Insurance (NI) - Employee only
        ni_threshold = 12570
        ni_lower = 0.08
        ni_upper = 0.02
        
        # Pension Contributions
        employee_pension = annual_income * (pension_contribution_percent / 100)
        
        # Income Tax Calculation
        taxable_income = annual_income - employee_pension
        if taxable_income <= personal_allowance:
            income_tax = 0
        elif taxable_income <= basic_rate_threshold:
            income_tax = (taxable_income - personal_allowance) * basic_rate
        elif taxable_income <= higher_rate_threshold:
            income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((taxable_income - basic_rate_threshold) * higher_rate)
        else:
            income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((higher_rate_threshold - basic_rate_threshold) * higher_rate) + ((taxable_income - higher_rate_threshold) * additional_rate)
        
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
        take_home_pay = annual_income - (income_tax + ni_contribution + student_loan_repayment + employee_pension)
        
        return {
            "Gross Income": round(annual_income),
            "Employee Pension": round(employee_pension),
            "Income Tax": round(income_tax),
            "Employee NI": round(ni_contribution),
            "Student Loan Repayment": round(student_loan_repayment),
            "Net Take-Home Pay": round(take_home_pay),
            "Working Days": working_days,
            "Daily Rate": pay_rate
        }

def generate_pdf(result, calculation_mode, client_rate=None, base_rate=None, pay_rate=None, margin=None, employer_deductions=None, status="Inside IR35"):
    """Generate PDF report with proper IR35 status handling"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Main title
    pdf.set_font("Arial", size=16, style='B')
    pdf.cell(200, 10, "IR35 Tax Calculation Results", ln=True, align='C')
    pdf.ln(10)
    
    # Rate Summary
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Rate Summary", ln=True)
    pdf.set_font("Arial", size=11)
    
    if status == "Outside IR35":
        pdf.cell(200, 8, f"Base Rate = Pay Rate: £{round(pay_rate)}", ln=True)
        pdf.cell(200, 8, f"Working Days: {result['Working Days']}", ln=True)
        pdf.cell(200, 8, f"Project Total: £{round(result['Project Total'])}", ln=True)
        if result['VAT Amount'] > 0:
            pdf.cell(200, 8, f"VAT Charged to Client (20%): £{round(result['VAT Amount'])}", ln=True)
    else:
        if calculation_mode == "Client Rate":
            pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
            pdf.cell(200, 8, f"Margin: {margin['Margin Percentage']}% (£{margin['Daily Margin']}/day)", ln=True)
            pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
        elif calculation_mode == "Base Rate":
            pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
            pdf.cell(200, 8, f"Margin: {margin['Margin Percentage']}% (£{margin['Daily Margin']}/day)", ln=True)
            pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
        else:
            pdf.cell(200, 8, f"Pay Rate: £{round(pay_rate)}", ln=True)
            pdf.cell(200, 8, f"Base Rate: £{round(base_rate)}", ln=True)
            pdf.cell(200, 8, f"Margin: {margin['Margin Percentage']}% (£{margin['Daily Margin']}/day)", ln=True)
            pdf.cell(200, 8, f"Client Rate: £{round(client_rate)}", ln=True)
    
    # Inside IR35 Deductions
    if status == "Inside IR35" and employer_deductions:
        pdf.ln(5)
        pdf.set_font("Arial", size=12, style='B')
        pdf.cell(200, 8, "Employer Deductions", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, f"Daily Employer NI (15%): £{employer_deductions['Daily Employer NI']}", ln=True)
        pdf.cell(200, 8, f"Daily Employer Pension (3%): £{employer_deductions['Daily Employer Pension']}", ln=True)
        pdf.cell(200, 8, f"Daily Apprentice Levy (0.5%): £{employer_deductions['Daily Apprentice Levy']}", ln=True)
        pdf.cell(200, 8, f"Total Employer NI: £{employer_deductions['Total Employer NI']}", ln=True)
        pdf.cell(200, 8, f"Total Employer Pension: £{employer_deductions['Total Employer Pension']}", ln=True)
        pdf.cell(200, 8, f"Total Apprentice Levy: £{employer_deductions['Total Apprentice Levy']}", ln=True)
        pdf.cell(200, 8, f"Total Employer Deductions: £{employer_deductions['Total Employer Deductions']}", ln=True)
    
    # Project Breakdown
    pdf.ln(5)
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 8, "Project Breakdown", ln=True)
    pdf.set_font("Arial", size=11)
    
    if status == "Inside IR35":
        daily_gross = pay_rate
        daily_net = result["Net Take-Home Pay"] / result["Working Days"]
        monthly_gross = daily_gross * 20
        monthly_net = daily_net * 20
        
        pdf.cell(200, 8, f"Daily Gross: £{round(daily_gross)}", ln=True)
        pdf.cell(200, 8, f"Daily Net: £{round(daily_net)}", ln=True)
        pdf.cell(200, 8, f"Monthly Gross (20 days): £{round(monthly_gross)}", ln=True)
        pdf.cell(200, 8, f"Monthly Net (20 days): £{round(monthly_net)}", ln=True)
        pdf.cell(200, 8, f"Project Gross Total: £{round(result['Gross Income'])}", ln=True)
        pdf.cell(200, 8, f"Project Net Total: £{round(result['Net Take-Home Pay'])}", ln=True)
        
        # Payslip Breakdown
        basic_rate, holiday_pay = calculate_holiday_components(pay_rate)
        pdf.ln(5)
        pdf.set_font("Arial", size=12, style='B')
        pdf.cell(200, 8, "Payslip Breakdown (Compliance)", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, f"Basic Daily Rate (excl. holiday pay): £{basic_rate}", ln=True)
        pdf.cell(200, 8, f"Holiday Pay (per day): £{holiday_pay}", ln=True)
    
    # Detailed Breakdown for Inside IR35
    if status == "Inside IR35":
        pdf.ln(5)
        pdf.set_font("Arial", size=12, style='B')
        pdf.cell(200, 8, "Detailed Breakdown", ln=True)
        pdf.set_font("Arial", size=11)
        
        pdf.cell(200, 8, f"Gross Income: £{result['Gross Income']}", ln=True)
        pdf.cell(200, 8, f"Income Tax: £{result['Income Tax']}", ln=True)
        pdf.cell(200, 8, f"Employee NI: £{result['Employee NI']}", ln=True)
        pdf.cell(200, 8, f"Employee Pension: £{result['Employee Pension']}", ln=True)
        if result.get('Student Loan Repayment', 0) > 0:
            pdf.cell(200, 8, f"Student Loan Repayment: £{result['Student Loan Repayment']}", ln=True)
    
    # Disclaimer
    pdf.ln(10)
    pdf.set_font("Arial", size=8)
    pdf.set_text_color(128, 128, 128)  # Grey color
    
    if status == "Outside IR35":
        pdf.cell(200, 8, "**Disclaimer:**", ln=True)
        pdf.multi_cell(190, 5, "As a self-employed consultant, you are responsible for calculating and paying your own taxes and National Insurance via Self Assessment. These figures show gross amounts only and do not constitute tax advice.")
    else:
        pdf.cell(200, 8, "**Disclaimer:**", ln=True)
        pdf.multi_cell(190, 5, "The figures provided are for illustrative purposes only and may vary depending on individual circumstances. This tool is not intended to provide tax, legal, or accounting advice. Consult a qualified professional for advice tailored to your situation.")
    
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

# Get UK bank holidays
bank_holidays = get_uk_bank_holidays()

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        # IR35 Status Selection
        st.session_state.status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            horizontal=True,
            help="Inside: Treated as employee. Outside: Self-employed",
            key="status_radio"
        )
        
        # Calculation Mode Selection
        st.session_state.calculation_mode = st.radio(
            "Start Calculation From:",
            ["Client Rate", "Base Rate", "Pay Rate"],
            horizontal=True,
            key="calculation_mode_radio"
        )
        
        # Dynamic inputs based on calculation mode
        if st.session_state.calculation_mode == "Client Rate":
            client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0, 
                value=800,
                step=50,
                help="The rate charged to the client",
                key="client_rate"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage",
                key="margin_percent"
            )
            base_rate = calculate_base_rate(client_rate, margin_percent)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            
        elif st.session_state.calculation_mode == "Base Rate":
            base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0, 
                value=500,
                step=50,
                help="The rate after margin deduction",
                key="base_rate"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage",
                key="margin_percent"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
            
        else:  # Pay Rate
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=400,
                step=50,
                help="The rate paid to consultant before employee deductions",
                key="pay_rate"
            )
            base_rate = calculate_base_rate_from_pay(pay_rate)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=23.0,
                step=0.5,
                help="Your company's margin percentage",
                key="margin_percent"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
        
        # Common inputs
        st.session_state.days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=4,
            help="Number of days worked each week",
            key="days_per_week_select"
        )
        
        st.session_state.start_date = st.date_input(
            "Project Start Date:",
            value=st.session_state.start_date,
            min_value=datetime.today().date() - timedelta(days=365),
            max_value=datetime.today().date() + timedelta(days=365*3),
            key="start_date_input"
        )
        
        st.session_state.end_date = st.date_input(
            "Project End Date:",
            value=st.session_state.end_date,
            min_value=datetime.today().date(),
            max_value=datetime.today().date() + timedelta(days=365*3),
            key="end_date_input"
        )
        
    with col2:
        # Calculate working days
        working_days = calculate_working_days(
            st.session_state.start_date, 
            st.session_state.end_date, 
            st.session_state.days_per_week, 
            bank_holidays
        )
        st.session_state.working_days = working_days
        st.write(f"**Calculated Working Days:** {working_days}")
        
        # Only show Pay Rate input if not already the starting point
        if st.session_state.calculation_mode != "Pay Rate":
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=round(calculate_pay_rate(base_rate)) if 'base_rate' in locals() else 400,
                step=50,
                help="The rate paid to consultant before employee deductions",
                disabled=st.session_state.calculation_mode != "Pay Rate",
                key="pay_rate_derived"
            )
        
        if st.session_state.status == "Inside IR35":
            st.session_state.employee_pension = st.number_input(
                "Employee Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employee_pension,
                step=0.5,
                help="Percentage of salary going to your pension",
                key="employee_pension_input"
            )
            
            st.session_state.employer_pension_percent = st.number_input(
                "Employer Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employer_pension_percent,
                step=0.5,
                help="Standard UK employer contribution is 3%+",
                key="employer_pension_input"
            )
            
            st.session_state.student_loan = st.selectbox(
                "Student Loan Plan:", 
                ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                help="Select your student loan repayment plan",
                key="student_loan_select"
            )
        else:  # Outside IR35
            st.session_state.vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=st.session_state.vat_registered,
                help="Check if you're VAT registered (outside IR35 only)",
                key="vat_registered_checkbox"
            )
    
    # Submit button for the form
    submitted = st.form_submit_button("Calculate")
    
    if submitted:
        if st.session_state.start_date >= st.session_state.end_date:
            st.error("End date must be after start date")
        else:
            # Store results in a dictionary first
            results_data = {
                "calculation_mode": st.session_state.calculation_mode,
                "results": ir35_tax_calculator(
                    pay_rate, 
                    st.session_state.working_days, 
                    st.session_state.employee_pension,
                    st.session_state.student_loan, 
                    st.session_state.status, 
                    st.session_state.vat_registered if st.session_state.status == "Outside IR35" else False
                ),
                "client_rate": client_rate if 'client_rate' in locals() else None,
                "base_rate": base_rate if 'base_rate' in locals() else None,
                "pay_rate": pay_rate,
                "working_days": st.session_state.working_days,
                "margin_percent": margin_percent if 'margin_percent' in locals() else None,
                "status": st.session_state.status
            }

            # Calculate additional data
            if st.session_state.status == "Inside IR35":
                results_data["employer_deductions"] = calculate_employer_deductions(base_rate, st.session_state.working_days)
            else:
                results_data["employer_deductions"] = None
            
            if 'client_rate' in locals() and 'base_rate' in locals():
                results_data["margin"] = calculate_margin(client_rate, base_rate, st.session_state.working_days)

            # Update session state safely
            for key, value in results_data.items():
                st.session_state[key] = value

# Results Display
if st.session_state.get('results'):
    st.subheader("Results")
    
    if st.session_state.status == "Outside IR35":
        # Outside IR35 Results
        st.write("### Outside IR35 - Self-Employed Consultant")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Base Rate = Pay Rate:** £{round(st.session_state.pay_rate)}")
            st.write(f"**Working Days:** {st.session_state.results['Working Days']}")
            st.write(f"**Project Total:** £{round(st.session_state.results['Project Total'])}")
        with col2:
            if st.session_state.results['VAT Amount'] > 0:
                st.write(f"**VAT Charged to Client (20%):** £{round(st.session_state.results['VAT Amount'])}")
        
        st.warning(st.session_state.results['Disclaimer'])
    else:
        # Inside IR35 Results
        st.write("### Rate Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.session_state.calculation_mode == "Client Rate":
                st.metric("Client Rate", f"£{round(st.session_state.client_rate)}")
            else:
                st.metric("Calculated Client Rate", f"£{round(st.session_state.client_rate)}")
        with col2:
            if st.session_state.calculation_mode == "Base Rate":
                st.metric("Base Rate", f"£{round(st.session_state.base_rate)}")
            else:
                st.metric("Calculated Base Rate", f"£{round(st.session_state.base_rate)}")
        with col3:
            st.metric("Pay Rate", f"£{round(st.session_state.pay_rate)}")
        
        # Margin and Employer Deductions
        st.write("### Margin & Deductions")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Margin Percentage:** {st.session_state.margin['Margin Percentage']}%")
            st.write(f"**Daily Margin:** £{st.session_state.margin['Daily Margin']}")
            st.write(f"**Total Margin:** £{st.session_state.margin['Total Margin']}")
        with col2:
            if st.session_state.employer_deductions:
                st.write("**Employer Deductions (Daily):**")
                st.write(f"- NI (15%): £{st.session_state.employer_deductions['Daily Employer NI']}")
                st.write(f"- Pension (3%): £{st.session_state.employer_deductions['Daily Employer Pension']}")
                st.write(f"- Levy (0.5%): £{st.session_state.employer_deductions['Daily Apprentice Levy']}")
                st.write("**Total Deductions:**")
                st.write(f"- NI: £{st.session_state.employer_deductions['Total Employer NI']}")
                st.write(f"- Pension: £{st.session_state.employer_deductions['Total Employer Pension']}")
                st.write(f"- Levy: £{st.session_state.employer_deductions['Total Apprentice Levy']}")
        
        # Time Period Breakdown
        st.write("### Project Breakdown")
        days_in_month = 20  # Standard assumption
        
        # Daily rates
        daily_gross = st.session_state.pay_rate
        daily_net = st.session_state.results["Net Take-Home Pay"] / st.session_state.working_days
        
        # Monthly rates (20 working days)
        monthly_gross = daily_gross * days_in_month
        monthly_net = daily_net * days_in_month
        
        # Project totals
        project_gross = daily_gross * st.session_state.working_days
        project_net = st.session_state.results["Net Take-Home Pay"]
        
        # Display in columns
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Daily Rates**")
            st.write(f"Gross: £{round(daily_gross)}")
            st.write(f"Net: £{round(daily_net)}")
        with col2:
            st.write("**Monthly Rates (20 days)**")
            st.write(f"Gross: £{round(monthly_gross)}")
            st.write(f"Net: £{round(monthly_net)}")
        with col3:
            st.write(f"**Project Total ({st.session_state.working_days} days)**")
            st.write(f"Gross: £{round(project_gross)}")
            st.write(f"Net: £{round(project_net)}")
        
        # Payslip Breakdown
        basic_rate, holiday_pay = calculate_holiday_components(st.session_state.pay_rate)
        st.write("### Payslip Breakdown (Compliance)")
        st.write(f"**Basic Daily Rate (excl. holiday pay):** £{basic_rate}")
        st.write(f"**Holiday Pay (per day):** £{holiday_pay}")
        st.caption("Note: These values are for compliance purposes only and not used in negotiations.")
        
        # Detailed Breakdown
        st.write("### Detailed Breakdown")
        for key, value in st.session_state.results.items():
            if key not in ["VAT Amount", "Working Days", "Disclaimer"]:
                st.write(f"**{key}:** £{value}")
    
    # Generate Report Button
    if st.button("Generate PDF Report"):
        pdf_data = generate_pdf(
            st.session_state.results,
            st.session_state.calculation_mode,
            st.session_state.client_rate,
            st.session_state.base_rate,
            st.session_state.pay_rate,
            st.session_state.margin,
            st.session_state.employer_deductions,
            st.session_state.status
        )
        st.download_button(
            "Download Report",
            data=pdf_data,
            file_name="IR35_Tax_Report.pdf",
            mime="application/pdf"
        )

# Comparison Mode
st.subheader("Comparison Mode")
st.session_state.compare_mode = st.checkbox("Enable Comparison Mode", key="compare_mode_checkbox")

if st.session_state.compare_mode:
    st.info("""
    **Comparison Explanation**: 
    - **Inside IR35**: Pay Rate is after employer deductions (NI 15%, Pension 3%, Levy 0.5%)
    - **Outside IR35**: Pay Rate equals Base Rate (no deductions)
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Scenario 1 - Inside IR35**")
        inside_pay_rate = st.number_input(
            "Pay Rate (£)", 
            value=400,
            step=50,
            key="inside_pay_rate"
        )
    
    with col2:
        st.write("**Scenario 2 - Outside IR35**")
        outside_base_rate = st.number_input(
            "Base Rate (£)", 
            value=500,
            step=50,
            key="outside_base_rate"
        )
        outside_vat = st.checkbox(
            "VAT Registered?", 
            value=False,
            key="outside_vat_checkbox"
        )
    
    if st.button("Compare Scenarios", key="compare_button"):
        # Calculate working days for comparison
        working_days = calculate_working_days(
            st.session_state.start_date,
            st.session_state.end_date,
            st.session_state.days_per_week,
            bank_holidays
        )
        
        # Inside IR35 scenario
        inside_base_rate = calculate_base_rate_from_pay(inside_pay_rate)
        inside_employer_deductions = calculate_employer_deductions(inside_base_rate, working_days)
        inside_result = ir35_tax_calculator(
            inside_pay_rate, working_days, 
            st.session_state.employee_pension,
            st.session_state.student_loan,
            "Inside IR35", False
        )
        
        # Outside IR35 scenario
        outside_result = ir35_tax_calculator(
            outside_base_rate, working_days, 
            0, "None", "Outside IR35", outside_vat
        )
        
        # Display comparison
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Inside IR35")
            st.write(f"**Pay Rate:** £{round(inside_pay_rate)}")
            st.write(f"**Base Rate:** £{round(inside_base_rate)}")
            st.write("**Employer Deductions (Daily):**")
            st.write(f"- NI (15%): £{inside_employer_deductions['Daily Employer NI']}")
            st.write(f"- Pension (3%): £{inside_employer_deductions['Daily Employer Pension']}")
            st.write(f"- Levy (0.5%): £{inside_employer_deductions['Daily Apprentice Levy']}")
            st.write(f"**Daily Net:** £{round(inside_result['Net Take-Home Pay']/working_days)}")
            st.write(f"**Project Net:** £{round(inside_result['Net Take-Home Pay'])}")
        
        with col2:
            st.write("### Outside IR35")
            st.write(f"**Base Rate = Pay Rate:** £{round(outside_base_rate)}")
            if outside_vat:
                st.write(f"**VAT Charged to Client (20%):** £{round(outside_result['VAT Amount'])}")
            st.write(f"**Project Total:** £{round(outside_result['Project Total'])}")
            st.warning("Self-employed consultants must calculate their own taxes")
        
        # Difference calculation
        difference = outside_result['Project Total'] - inside_result['Net Take-Home Pay']
        st.write(f"**Gross Difference (Outside - Inside):** £{round(difference)}")
