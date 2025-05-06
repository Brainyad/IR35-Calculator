import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import math
import pandas as pd

# Company Colors
GREY = "#515D7A"
ORANGE = "#F39200"
LIGHT_GREY = "#F5F5F5"
WHITE = "#FFFFFF"

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
        'client_rate': 800.0,
        'base_rate': 500.0,
        'pay_rate': 400.0,
        'margin_percent': 23.0,
        'employer_deductions': None,
        'margin': None,
        'inside_scenario': None,
        'outside_scenario': None
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
    
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    return (full_weeks * days_per_week) + min(remaining_days, days_per_week)

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

def styled_dataframe(df, title=""):
    """Apply company styling to a dataframe"""
    return df.style.set_table_styles([
        {'selector': 'thead', 'props': [('background-color', GREY), ('color', WHITE)]},
        {'selector': 'tbody tr:nth-child(even)', 'props': [('background-color', LIGHT_GREY)]},
        {'selector': 'tbody tr:nth-child(odd)', 'props': [('background-color', WHITE)]},
        {'selector': 'th.col_heading', 'props': [('text-align', 'left')]},
        {'selector': 'td', 'props': [('text-align', 'left')]},
        {'selector': '', 'props': [('border', f'1px solid {GREY}')]}
    ]).set_caption(title)

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
st.set_page_config(page_title="IR35 Tax Calculator", layout="wide", page_icon="📊")

# Custom CSS for styling
st.markdown(f"""
    <style>
        .main {{
            background-color: {WHITE};
        }}
        .stButton>button {{
            background-color: {GREY};
            color: white;
            border: none;
        }}
        .stButton>button:hover {{
            background-color: {ORANGE};
            color: white;
        }}
        .stRadio>div>div {{
            background-color: {LIGHT_GREY};
            padding: 10px;
            border-radius: 5px;
        }}
        .stNumberInput>div>div>input {{
            background-color: {LIGHT_GREY};
        }}
        .stSelectbox>div>div>select {{
            background-color: {LIGHT_GREY};
        }}
        .stDateInput>div>div>input {{
            background-color: {LIGHT_GREY};
        }}
        .css-1aumxhk {{
            background-color: {GREY};
            color: white;
        }}
        h1, h2, h3 {{
            color: {GREY};
        }}
        .dataframe {{
            width: auto !important;
        }}
        .stDataFrame {{
            width: auto !important;
        }}
    </style>
    """, unsafe_allow_html=True)

# Add company logo
try:
    logo = Image.open("B2e Logo.png")
    st.image(logo, width=200)
except:
    st.write("")

st.title("IR35 Tax Calculator")

# Get UK bank holidays
bank_holidays = get_uk_bank_holidays()

# Configuration options
with st.container():
    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state.calculation_mode = st.radio(
            "Start Calculation From:",
            ["Client Rate", "Base Rate", "Pay Rate"],
            index=["Client Rate", "Base Rate", "Pay Rate"].index(st.session_state.calculation_mode),
            key="calculation_mode_config"
        )
    with col2:
        st.session_state.status = st.radio(
            "IR35 Status", 
            ["Inside IR35", "Outside IR35"], 
            index=0 if st.session_state.status == "Inside IR35" else 1,
            key="status_config"
        )

# Main Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        # Dynamic inputs based on calculation mode
        if st.session_state.calculation_mode == "Client Rate":
            st.session_state.client_rate = st.number_input(
                "Client Charge Rate (£):", 
                min_value=0.0, 
                value=float(st.session_state.client_rate),
                step=50.0,
                format="%.2f",
                key="client_rate_input"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=float(st.session_state.margin_percent),
                step=0.5,
                format="%.1f",
                key="margin_percent_input"
            )
            
        elif st.session_state.calculation_mode == "Base Rate":
            st.session_state.base_rate = st.number_input(
                "Base Rate (£):", 
                min_value=0.0, 
                value=float(st.session_state.base_rate),
                step=50.0,
                format="%.2f",
                key="base_rate_input"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=float(st.session_state.margin_percent),
                step=0.5,
                format="%.1f",
                key="margin_percent_input"
            )
            
        else:  # Pay Rate
            st.session_state.pay_rate = st.number_input(
                "Pay Rate (£):", 
                min_value=0.0, 
                value=float(st.session_state.pay_rate),
                step=50.0,
                format="%.2f",
                key="pay_rate_input"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):", 
                min_value=0.0, 
                max_value=100.0, 
                value=float(st.session_state.margin_percent),
                step=0.5,
                format="%.1f",
                key="margin_percent_input"
            )
        
        # Common inputs
        st.session_state.days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=st.session_state.days_per_week - 1,
            key="days_per_week_select"
        )
        
    with col2:
        st.session_state.start_date = st.date_input(
            "Project Start Date:",
            value=st.session_state.start_date,
            key="start_date_input"
        )
        
        st.session_state.end_date = st.date_input(
            "Project End Date:",
            value=st.session_state.end_date,
            key="end_date_input"
        )
        
        if st.session_state.status == "Inside IR35":
            st.session_state.employee_pension = st.number_input(
                "Employee Pension Contribution (%):", 
                min_value=0.0, 
                value=float(st.session_state.employee_pension),
                step=0.5,
                format="%.1f",
                key="employee_pension_input"
            )
            
            st.session_state.student_loan = st.selectbox(
                "Student Loan Plan:", 
                ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                index=["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"].index(st.session_state.student_loan),
                key="student_loan_select"
            )
        else:
            st.session_state.vat_registered = st.checkbox(
                "VAT Registered? (20%)", 
                value=st.session_state.vat_registered,
                key="vat_registered_checkbox"
            )
    
    # Submit button
    submitted = st.form_submit_button("Calculate", use_container_width=True)
    
    if submitted:
        if st.session_state.start_date >= st.session_state.end_date:
            st.error("End date must be after start date")
        else:
            try:
                # Calculate working days
                st.session_state.working_days = calculate_working_days(
                    st.session_state.start_date,
                    st.session_state.end_date,
                    st.session_state.days_per_week,
                    bank_holidays
                )
                
                # Calculate rates based on calculation mode
                if st.session_state.calculation_mode == "Client Rate":
                    st.session_state.base_rate = calculate_base_rate(
                        float(st.session_state.client_rate),
                        float(st.session_state.margin_percent)
                    )
                    st.session_state.pay_rate = calculate_pay_rate(float(st.session_state.base_rate))
                elif st.session_state.calculation_mode == "Base Rate":
                    st.session_state.client_rate = calculate_client_rate(
                        float(st.session_state.base_rate),
                        float(st.session_state.margin_percent)
                    )
                    st.session_state.pay_rate = calculate_pay_rate(float(st.session_state.base_rate))
                elif st.session_state.calculation_mode == "Pay Rate":
                    st.session_state.base_rate = calculate_base_rate_from_pay(float(st.session_state.pay_rate))
                    st.session_state.client_rate = calculate_client_rate(
                        float(st.session_state.base_rate),
                        float(st.session_state.margin_percent)
                    )
                
                # Calculate results
                st.session_state.results = ir35_tax_calculator(
                    float(st.session_state.pay_rate),
                    st.session_state.working_days,
                    float(st.session_state.employee_pension) if st.session_state.status == "Inside IR35" else 0.0,
                    st.session_state.student_loan if st.session_state.status == "Inside IR35" else "None",
                    st.session_state.status,
                    st.session_state.vat_registered if st.session_state.status == "Outside IR35" else False
                )
                
                # Calculate margin and deductions for both Inside and Outside IR35
                st.session_state.margin = calculate_margin(
                    float(st.session_state.client_rate),
                    float(st.session_state.base_rate),
                    st.session_state.working_days
                )
                
                if st.session_state.status == "Inside IR35":
                    st.session_state.employer_deductions = calculate_employer_deductions(
                        float(st.session_state.base_rate),
                        st.session_state.working_days
                    )
                else:
                    st.session_state.employer_deductions = None
                    
            except Exception as e:
                st.error(f"An error occurred during calculation: {str(e)}")

# Results Display
if st.session_state.get('results'):
    st.subheader("Results")
    
    # Rate Summary (shown for both Inside and Outside IR35)
    st.write("### Rate Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Client Rate", f"£{round(st.session_state.client_rate)}")
    with col2:
        st.metric("Base Rate", f"£{round(st.session_state.base_rate)}")
    with col3:
        st.metric("Pay Rate", f"£{round(st.session_state.pay_rate)}")
    
    # Margin information (shown for both Inside and Outside IR35)
    st.write("### Margin Information")
    margin_data = [
        ["Margin Percentage", f"{st.session_state.margin['Margin Percentage']}%"],
        ["Daily Margin", f"£{st.session_state.margin['Daily Margin']}"],
        ["Total Margin", f"£{st.session_state.margin['Total Margin']}"]
    ]
    df_margin = pd.DataFrame(margin_data, columns=["Metric", "Value"])
    st.dataframe(styled_dataframe(df_margin), use_container_width=True)
    
    if st.session_state.status == "Outside IR35":
        # Outside IR35 Results
        st.write("### Project Summary")
        summary_data = [
            ["Working Days", st.session_state.results['Working Days']],
            ["Project Total", f"£{round(st.session_state.results['Project Total'])}"]
        ]
        
        if st.session_state.results['VAT Amount'] > 0:
            summary_data.append(["VAT Charged to Client (20%)", f"£{round(st.session_state.results['VAT Amount'])}"])
        
        df_summary = pd.DataFrame(summary_data, columns=["Metric", "Value"])
        st.dataframe(styled_dataframe(df_summary), use_container_width=True)
        
        st.warning(st.session_state.results['Disclaimer'])
    else:
        # Inside IR35 Results
        if st.session_state.employer_deductions:
            st.write("### Employer Deductions")
            deductions_data = [
                ["Daily Employer NI (15%)", f"£{st.session_state.employer_deductions['Daily Employer NI']}"],
                ["Daily Employer Pension (3%)", f"£{st.session_state.employer_deductions['Daily Employer Pension']}"],
                ["Daily Apprentice Levy (0.5%)", f"£{st.session_state.employer_deductions['Daily Apprentice Levy']}"],
                ["Total Employer NI", f"£{st.session_state.employer_deductions['Total Employer NI']}"],
                ["Total Employer Pension", f"£{st.session_state.employer_deductions['Total Employer Pension']}"],
                ["Total Apprentice Levy", f"£{st.session_state.employer_deductions['Total Apprentice Levy']}"],
                ["Total Employer Deductions", f"£{st.session_state.employer_deductions['Total Employer Deductions']}"]
            ]
            df_deductions = pd.DataFrame(deductions_data, columns=["Deduction", "Amount"])
            st.dataframe(styled_dataframe(df_deductions), use_container_width=True)
        
        # Time Period Breakdown
        st.write("### Project Breakdown")
        days_in_month = 20  # Standard assumption
        
        # Create breakdown data
        breakdown_data = [
            ["Daily Rates", f"£{round(st.session_state.pay_rate)}", f"£{round(st.session_state.results['Net Take-Home Pay'] / st.session_state.working_days)}"],
            ["Monthly Rates (20 days)", f"£{round(st.session_state.pay_rate * days_in_month)}", f"£{round((st.session_state.results['Net Take-Home Pay'] / st.session_state.working_days) * days_in_month)}"],
            [f"Project Total ({st.session_state.working_days} days)", f"£{round(st.session_state.pay_rate * st.session_state.working_days)}", f"£{round(st.session_state.results['Net Take-Home Pay'])}"]
        ]
        df_breakdown = pd.DataFrame(breakdown_data, columns=["Period", "Gross", "Net"])
        st.dataframe(styled_dataframe(df_breakdown), use_container_width=True)
        
        # Payslip Breakdown
        basic_rate, holiday_pay = calculate_holiday_components(st.session_state.pay_rate)
        st.write("### Payslip Breakdown (Compliance)")
        payslip_data = [
            ["Basic Daily Rate (excl. holiday pay)", f"£{basic_rate}"],
            ["Holiday Pay (per day)", f"£{holiday_pay}"]
        ]
        df_payslip = pd.DataFrame(payslip_data, columns=["Component", "Amount"])
        st.dataframe(styled_dataframe(df_payslip), use_container_width=True)
        st.caption("Note: These values are for compliance purposes only and not used in negotiations.")
        
        # Detailed Breakdown
        st.write("### Detailed Breakdown")
        breakdown_items = []
        for key, value in st.session_state.results.items():
            if key not in ["VAT Amount", "Working Days", "Disclaimer"]:
                breakdown_items.append([key.replace("_", " ").title(), f"£{value}"])
        
        df_details = pd.DataFrame(breakdown_items, columns=["Item", "Amount"])
        st.dataframe(styled_dataframe(df_details), use_container_width=True)
    
    # Generate Report Button
    if st.button("Generate PDF Report", use_container_width=True):
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
            mime="application/pdf",
            use_container_width=True
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
            value=400.0,
            step=50.0,
            format="%.2f",
            key="inside_pay_rate"
        )
    
    with col2:
        st.write("**Scenario 2 - Outside IR35**")
        outside_base_rate = st.number_input(
            "Base Rate (£)", 
            value=500.0,
            step=50.0,
            format="%.2f",
            key="outside_base_rate"
        )
        outside_vat = st.checkbox(
            "VAT Registered?", 
            value=False,
            key="outside_vat_checkbox"
        )
    
    if st.button("Compare Scenarios", key="compare_button", use_container_width=True):
        try:
            # Calculate working days for comparison
            working_days = calculate_working_days(
                st.session_state.start_date,
                st.session_state.end_date,
                st.session_state.days_per_week,
                bank_holidays
            )
            
            # Inside IR35 scenario
            inside_base_rate = calculate_base_rate_from_pay(inside_pay_rate)
            inside_client_rate = calculate_client_rate(
                inside_base_rate,
                st.session_state.margin_percent
            )
            inside_employer_deductions = calculate_employer_deductions(inside_base_rate, working_days)
            inside_margin = calculate_margin(
                inside_client_rate,
                inside_base_rate,
                working_days
            )
            inside_result = ir35_tax_calculator(
                inside_pay_rate, working_days, 
                st.session_state.employee_pension,
                st.session_state.student_loan,
                "Inside IR35", False
            )
            
            # Outside IR35 scenario
            outside_client_rate = calculate_client_rate(
                outside_base_rate,
                st.session_state.margin_percent
            )
            outside_margin = calculate_margin(
                outside_client_rate,
                outside_base_rate,
                working_days
            )
            outside_result = ir35_tax_calculator(
                outside_base_rate,
