import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import math

# Initialize all session state variables with proper defaults
def initialize_session_state():
    default_state = {
        'results': None,
        'compare_mode': False,
        'calculation_mode': "Client Rate",
        'status': "Inside IR35",
        'working_days': 0,
        'employer_pension_percent': 3.0,
        'employee_pension': 5.0,
        'student_loan': "None",
        'days_per_week': 5,
        'start_date': datetime.today().date(),
        'end_date': (datetime.today() + timedelta(days=180)).date(),
        'vat_registered': False,
        'client_rate': 800,
        'base_rate': 500,
        'pay_rate': 400,
        'margin_percent': 23.0,
        'employer_deductions': None,
        'margin': None
    }
    
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

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
    return base_rate / 1.185  # 15% NI + 3% Pension + 0.5% Levy = 18.5%

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
        annual_income = pay_rate * working_days
        personal_allowance = 12570
        basic_rate_threshold = 50270
        higher_rate_threshold = 125140
        
        # Tax bands
        basic_rate = 0.2
        higher_rate = 0.4
        additional_rate = 0.45
        
        # National Insurance (NI)
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
        status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            index=0 if st.session_state.status == "Inside IR35" else 1,
            horizontal=True,
            key="status_radio"
        )
        
        # Calculation Mode Selection
        calculation_mode = st.radio(
            "Start Calculation From:",
            ["Client Rate", "Base Rate", "Pay Rate"],
            index=["Client Rate", "Base Rate", "Pay Rate"].index(st.session_state.calculation_mode),
            horizontal=True,
            key="calculation_mode_radio"
        )
        
        # Dynamic inputs based on calculation mode
        if calculation_mode == "Client Rate":
            client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0, 
                value=st.session_state.client_rate,
                step=50,
                key="client_rate_input"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            base_rate = calculate_base_rate(client_rate, margin_percent)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            
        elif calculation_mode == "Base Rate":
            base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0, 
                value=st.session_state.base_rate,
                step=50,
                key="base_rate_input"
            )
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
            
        else:  # Pay Rate
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=st.session_state.pay_rate,
                step=50,
                key="pay_rate_input"
            )
            base_rate = calculate_base_rate_from_pay(pay_rate)
            st.write(f"**Calculated Base Rate:** £{round(base_rate)}")
            margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.margin_percent,
                step=0.5,
                key="margin_percent_input"
            )
            client_rate = calculate_client_rate(base_rate, margin_percent)
            st.write(f"**Calculated Client Rate:** £{round(client_rate)}")
        
        # Common inputs
        days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=st.session_state.days_per_week - 1,
            key="days_per_week_select"
        )
        
        start_date = st.date_input(
            "Project Start Date:",
            value=st.session_state.start_date,
            key="start_date_input"
        )
        
        end_date = st.date_input(
            "Project End Date:",
            value=st.session_state.end_date,
            key="end_date_input"
        )
        
    with col2:
        # Calculate working days
        working_days = calculate_working_days(start_date, end_date, days_per_week, bank_holidays)
        st.write(f"**Calculated Working Days:** {working_days}")
        
        # Pay Rate input when not in Pay Rate mode
        if calculation_mode != "Pay Rate":
            pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0, 
                value=round(calculate_pay_rate(base_rate)) if 'base_rate' in locals() else st.session_state.pay_rate,
                step=50,
                key="pay_rate_derived"
            )
        
        if status == "Inside IR35":
            employee_pension = st.number_input(
                "Employee Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employee_pension,
                step=0.5,
                key="employee_pension_input"
            )
            
            employer_pension_percent = st.number_input(
                "Employer Pension Contribution (%):", 
                min_value=0.0, 
                value=st.session_state.employer_pension_percent,
                step=0.5,
                key="employer_pension_input"
            )
            
            student_loan = st.selectbox(
                "Student Loan Plan:", 
                ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                index=["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"].index(st.session_state.student_loan),
                key="student_loan_select"
            )
        else:
            vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=st.session_state.vat_registered,
                key="vat_registered_checkbox"
            )
    
    submitted = st.form_submit_button("Calculate")
    
    if submitted:
        if start_date >= end_date:
            st.error("End date must be after start date")
        else:
            try:
                # Update all session state variables at once
                new_state = {
                    'status': status,
                    'calculation_mode': calculation_mode,
                    'days_per_week': days_per_week,
                    'start_date': start_date,
                    'end_date': end_date,
                    'working_days': working_days,
                    'employee_pension': employee_pension if status == "Inside IR35" else 0,
                    'employer_pension_percent': employer_pension_percent if status == "Inside IR35" else 0,
                    'student_loan': student_loan if status == "Inside IR35" else "None",
                    'vat_registered': vat_registered if status == "Outside IR35" else False,
                    'client_rate': client_rate if 'client_rate' in locals() else st.session_state.client_rate,
                    'base_rate': base_rate if 'base_rate' in locals() else st.session_state.base_rate,
                    'pay_rate': pay_rate,
                    'margin_percent': margin_percent if 'margin_percent' in locals() else st.session_state.margin_percent
                }
                
                # Calculate results
                results = ir35_tax_calculator(
                    pay_rate,
                    working_days,
                    employee_pension if status == "Inside IR35" else 0,
                    student_loan if status == "Inside IR35" else "None",
                    status,
                    vat_registered if status == "Outside IR35" else False
                )
                
                new_state['results'] = results
                
                if status == "Inside IR35":
                    new_state['employer_deductions'] = calculate_employer_deductions(base_rate, working_days)
                    new_state['margin'] = calculate_margin(
                        client_rate if calculation_mode == "Client Rate" else calculate_client_rate(base_rate, margin_percent),
                        base_rate,
                        working_days
                    )
                else:
                    new_state['employer_deductions'] = None
                    new_state['margin'] = None
                
                # Update session state safely
                for key, value in new_state.items():
                    st.session_state[key] = value
                    
            except Exception as e:
                st.error(f"An error occurred during calculation: {str(e)}")

# [Rest of your code for results display, comparison mode, etc.]
# Make sure all references to variables use st.session_state
