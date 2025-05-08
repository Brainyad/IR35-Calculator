# ======================
# IR35 TAX CALCULATOR
# Final Version 5.0
# ======================

import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta
import pandas as pd

# ----------
# CONSTANTS
# ----------
GREY = "#515D7A"
ORANGE = "#F39200"
LIGHT_GREY = "#F5F5F5"
WHITE = "#FFFFFF"

TOOLTIPS = {
    "client_rate": "The daily rate charged to your end client (before deductions)",
    "base_rate": "Rate before employer deductions (Client Rate minus Margin)",
    "pay_rate": "Your gross daily pay before tax/NI deductions",
    "margin_percent": "Agency/umbrella company's percentage margin",
    "working_days": "Calculated days excluding weekends and bank holidays",
    "employee_pension": "Your personal pension contribution (default 5%)",
    "student_loan": "Select your student loan repayment plan if applicable",
    "vat_registered": "Whether VAT registered (Outside IR35 only)",
    "employer_pension": "Mandatory employer pension contribution (3% minimum)",
    "holiday_pay": "Statutory holiday pay included (Inside IR35)"
    
}

# ----------
# SESSION STATE
# ----------
def initialize_session_state():
    if 'initialized' not in st.session_state:
        defaults = {
            'results': None,
            'compare_mode': False,
            'calculation_mode': "Client Rate",
            'status': "Inside IR35",
            'working_days': 0,
            'employee_pension': 5.0,
            'employer_pension_percent': 3.0,
            'student_loan': "None",
            'days_per_week': 5,
            'start_date': datetime.today().date(),
            'end_date': (datetime.today() + timedelta(days=180)).date(),
            'vat_registered': False,
            'client_rate': 800.0,
            'base_rate': 500.0,
            'pay_rate': 400.0,
            'margin_percent': 23.0,
            'margin': None,
            'initialized': True
        }
        for key, value in defaults.items():
            st.session_state[key] = value

# ----------
# CALCULATION FUNCTIONS
# ----------
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
    basic_daily_rate = pay_rate / (1 + 0.1454)
    holiday_pay = pay_rate - basic_daily_rate
    return round(basic_daily_rate), round(holiday_pay)

def calculate_base_rate(client_rate, margin_percent):
    return client_rate * (1 - margin_percent/100)

def calculate_client_rate(base_rate, margin_percent):
    return base_rate / (1 - margin_percent/100)

def calculate_pay_rate(base_rate, status="Inside IR35"):
    return base_rate / 1.185 if status == "Inside IR35" else base_rate

def calculate_base_rate_from_pay(pay_rate, status="Inside IR35"):
    return pay_rate * 1.185 if status == "Inside IR35" else pay_rate

def calculate_employer_deductions(base_rate, working_days):
    daily_ni = base_rate * 0.15
    daily_pension = base_rate * (st.session_state.employer_pension_percent / 100)
    daily_levy = base_rate * 0.005
    return {
        "Daily Employer NI": round(daily_ni),
        "Daily Employer Pension": round(daily_pension),
        "Daily Apprentice Levy": round(daily_levy),
        "Total Employer NI": round(daily_ni * working_days),
        "Total Employer Pension": round(daily_pension * working_days),
        "Total Apprentice Levy": round(daily_levy * working_days),
        "Total Employer Deductions": round((daily_ni + daily_pension + daily_levy) * working_days)
    }

def calculate_margin(client_rate, base_rate, working_days):
    daily_margin = client_rate - base_rate
    margin_percent = ((client_rate - base_rate) / client_rate) * 100
    return {
        "Daily Margin": round(daily_margin),
        "Total Margin": round(daily_margin * working_days),
        "Margin Percentage": round(margin_percent, 1)
    }

def ir35_tax_calculator(pay_rate, working_days, pension_contribution_percent=5,
                       student_loan_plan="None", status="Inside IR35", vat_registered=False):
    if status == "Outside IR35":
        annual_income = pay_rate * working_days
        vat_amount = annual_income * 0.2 if vat_registered else 0
        return {
            "Base Rate": pay_rate,
            "Pay Rate": pay_rate,
            "VAT Amount": round(vat_amount),
            "Working Days": working_days,
            "Project Total": round(annual_income),
            "Daily Rate": round(pay_rate),
            "Disclaimer": "As a self-employed consultant, you are responsible for calculating and paying your own taxes and National Insurance via Self Assessment. These figures show gross amounts only."
        }
    else:
        annual_income = pay_rate * working_days
        personal_allowance = 12570
        basic_rate_threshold = 50270
        higher_rate_threshold = 125140
        
        # Tax calculations
        taxable_income = annual_income - (annual_income * (pension_contribution_percent / 100))
        if taxable_income <= personal_allowance:
            income_tax = 0
        elif taxable_income <= basic_rate_threshold:
            income_tax = (taxable_income - personal_allowance) * 0.2
        elif taxable_income <= higher_rate_threshold:
            income_tax = (basic_rate_threshold - personal_allowance) * 0.2 + (taxable_income - basic_rate_threshold) * 0.4
        else:
            income_tax = (basic_rate_threshold - personal_allowance) * 0.2 + (higher_rate_threshold - basic_rate_threshold) * 0.4 + (taxable_income - higher_rate_threshold) * 0.45
        
        # National Insurance
        ni_threshold = 12570
        if annual_income <= ni_threshold:
            ni_contribution = 0
        elif annual_income <= basic_rate_threshold:
            ni_contribution = (annual_income - ni_threshold) * 0.08
        else:
            ni_contribution = (basic_rate_threshold - ni_threshold) * 0.08 + (annual_income - basic_rate_threshold) * 0.02
        
        # Student Loan
        student_loan_repayment = 0
        if student_loan_plan == "Plan 1" and annual_income > 22015:
            student_loan_repayment = (annual_income - 22015) * 0.09
        elif student_loan_plan in ["Plan 2", "Plan 5"] and annual_income > 27295:
            student_loan_repayment = (annual_income - 27295) * 0.09
        elif student_loan_plan == "Plan 4" and annual_income > 31395:
            student_loan_repayment = (annual_income - 31395) * 0.09
        elif student_loan_plan == "Postgraduate Loan" and annual_income > 21000:
            student_loan_repayment = (annual_income - 21000) * 0.06
        
        take_home_pay = annual_income - (income_tax + ni_contribution + student_loan_repayment + (annual_income * (pension_contribution_percent / 100)))
        
        return {
            "Gross Income": round(annual_income),
            "Employee Pension": round(annual_income * (pension_contribution_percent / 100)),
            "Income Tax": round(income_tax),
            "Employee NI": round(ni_contribution),
            "Student Loan Repayment": round(student_loan_repayment),
            "Net Take-Home Pay": round(take_home_pay),
            "Working Days": working_days,
            "Daily Rate": round(pay_rate)
        }

# ----------
# PDF GENERATION
# ----------
def generate_pdf(result, calculation_mode, client_rate=None, base_rate=None, 
               pay_rate=None, margin=None, employer_deductions=None, status="Inside IR35"):
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
        pdf.cell(200, 8, f"Daily Employer Pension: £{employer_deductions['Daily Employer Pension']}", ln=True)
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
        daily_net = result["Net Take-Home Pay"] / result["Working Days"]
        pdf.cell(200, 8, f"Daily Gross: £{round(pay_rate)}", ln=True)
        pdf.cell(200, 8, f"Daily Net: £{round(daily_net)}", ln=True)
        pdf.cell(200, 8, f"Monthly Gross (20 days): £{round(pay_rate * 20)}", ln=True)
        pdf.cell(200, 8, f"Monthly Net (20 days): £{round(daily_net * 20)}", ln=True)
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
    
    # Detailed Breakdown
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
    pdf.set_text_color(128, 128, 128)
    pdf.cell(200, 8, "**Disclaimer:**", ln=True)
    if status == "Outside IR35":
        pdf.multi_cell(190, 5, "As a self-employed consultant, you are responsible for calculating and paying your own taxes and National Insurance via Self Assessment. These figures show gross amounts only and do not constitute tax advice.")
    else:
        pdf.multi_cell(190, 5, "The figures provided are for illustrative purposes only and may vary depending on individual circumstances. This tool is not intended to provide tax, legal, or accounting advice. Consult a qualified professional for advice tailored to your situation.")
    
    return pdf.output(dest='S').encode('latin1')

# ----------
# STREAMLIT UI
# ----------
def styled_dataframe(df, title=""):
    return df.style.set_table_styles([
        {'selector': 'thead', 'props': [('background-color', GREY), ('color', WHITE)]},
        {'selector': 'tbody tr:nth-child(even)', 'props': [('background-color', LIGHT_GREY)]},
        {'selector': 'tbody tr:nth-child(odd)', 'props': [('background-color', WHITE)]},
        {'selector': 'th.col_heading', 'props': [('text-align', 'left')]},
        {'selector': 'td', 'props': [('text-align', 'left')]},
        {'selector': '', 'props': [('border', f'1px solid {GREY}')]}
    ]).set_caption(title)

def main():
    st.set_page_config(
        page_title="IR35 Tax Calculator", 
        layout="centered",
        page_icon="📊"
    )
    
    # Clean CSS styling
    st.markdown(f"""
        <style>
            .main {{
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
            }}
            .stButton>button {{
                background-color: {GREY};
                color: white;
                border: none;
            }}
            .stButton>button:hover {{
                background-color: {ORANGE};
            }}
            .stNumberInput, .stSelectbox, .stDateInput {{
                margin-bottom: 1rem;
            }}
            h1, h2, h3 {{
                color: {GREY};
            }}
        </style>
    """, unsafe_allow_html=True)

    # Logo with fixed sizing
    try:
        logo = Image.open("B2e Logo.png")
        st.image(logo, width=200, use_container_width=False)
    except:
        st.write("")

    st.title("IR35 Tax Calculator")
    bank_holidays = get_uk_bank_holidays()
    initialize_session_state()

    # Mode selection
    with st.container():
        col1, col2 = st.columns([1, 1])
        with col1:
            st.session_state.calculation_mode = st.radio(
                "Start Calculation From:",
                ["Client Rate", "Base Rate", "Pay Rate"],
                index=["Client Rate", "Base Rate", "Pay Rate"].index(st.session_state.calculation_mode)
            )
        with col2:
            st.session_state.status = st.radio(
                "IR35 Status", 
                ["Inside IR35", "Outside IR35"], 
                index=0 if st.session_state.status == "Inside IR35" else 1,
                help="Inside IR35: PAYE employment | Outside IR35: Self-employed"
            )

    # Main calculator form
    with st.form("calculator_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state.calculation_mode == "Client Rate":
                st.session_state.client_rate = st.number_input(
                    "Client Rate (£):",
                    min_value=0.0,
                    value=float(st.session_state.client_rate),
                    step=50.0,
                    help=TOOLTIPS["client_rate"]
                )
                st.session_state.margin_percent = st.number_input(
                    "Margin (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.margin_percent),
                    step=0.5,
                    help=TOOLTIPS["margin_percent"]
                )
            elif st.session_state.calculation_mode == "Base Rate":
                st.session_state.base_rate = st.number_input(
                    "Base Rate (£):",
                    min_value=0.0,
                    value=float(st.session_state.base_rate),
                    step=50.0,
                    help=TOOLTIPS["base_rate"]
                )
                st.session_state.margin_percent = st.number_input(
                    "Margin (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.margin_percent),
                    step=0.5,
                    help=TOOLTIPS["margin_percent"]
                )
            else:
                st.session_state.pay_rate = st.number_input(
                    "Pay Rate (£):",
                    min_value=0.0,
                    value=float(st.session_state.pay_rate),
                    step=50.0,
                    help=TOOLTIPS["pay_rate"]
                )
                st.session_state.margin_percent = st.number_input(
                    "Margin (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.margin_percent),
                    step=0.5,
                    help=TOOLTIPS["margin_percent"]
                )
            
            st.session_state.days_per_week = st.selectbox(
                "Days worked per week:",
                [1, 2, 3, 4, 5],
                index=st.session_state.days_per_week - 1,
                help=TOOLTIPS["working_days"]
            )
        
        with col2:
            st.session_state.start_date = st.date_input(
                "Project Start Date:",
                value=st.session_state.start_date
            )
            
            st.session_state.end_date = st.date_input(
                "Project End Date:",
                value=st.session_state.end_date
            )
            
            if st.session_state.status == "Inside IR35":
                st.session_state.employee_pension = st.number_input(
                    "Employee Pension (%):", 
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.employee_pension),
                    step=0.5,
                    help=TOOLTIPS["employee_pension"]
                )
                st.session_state.employer_pension_percent = st.number_input(
                "Employer Pension (%):",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.employer_pension_percent),
                step=0.5,
                help=TOOLTIPS["employer_pension"]
                )
                st.session_state.student_loan = st.selectbox(
                    "Student Loan Plan:", 
                    ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                    index=["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"].index(st.session_state.student_loan),
                    help=TOOLTIPS["student_loan"]
                )
            else:
                st.session_state.vat_registered = st.checkbox(
                    "VAT Registered? (20%)", 
                    value=st.session_state.vat_registered,
                    help=TOOLTIPS["vat_registered"]
                )
        
        submitted = st.form_submit_button("Calculate")
        
        if submitted:
            if st.session_state.start_date >= st.session_state.end_date:
                st.error("End date must be after start date")
            else:
                try:
                    st.session_state.working_days = calculate_working_days(
                        st.session_state.start_date,
                        st.session_state.end_date,
                        st.session_state.days_per_week,
                        bank_holidays
                    )
                    
                    if st.session_state.calculation_mode == "Client Rate":
                        st.session_state.base_rate = calculate_base_rate(
                            float(st.session_state.client_rate),
                            float(st.session_state.margin_percent)
                        )
                        st.session_state.pay_rate = calculate_pay_rate(
                            float(st.session_state.base_rate),
                            st.session_state.status
                        )
                    elif st.session_state.calculation_mode == "Base Rate":
                        st.session_state.client_rate = calculate_client_rate(
                            float(st.session_state.base_rate),
                            float(st.session_state.margin_percent)
                        )
                        st.session_state.pay_rate = calculate_pay_rate(
                            float(st.session_state.base_rate),
                            st.session_state.status
                        )
                    else:
                        st.session_state.base_rate = calculate_base_rate_from_pay(
                            float(st.session_state.pay_rate),
                            st.session_state.status
                        )
                        st.session_state.client_rate = calculate_client_rate(
                            float(st.session_state.base_rate),
                            float(st.session_state.margin_percent)
                        )
                    
                    st.session_state.results = ir35_tax_calculator(
                        float(st.session_state.pay_rate),
                        st.session_state.working_days,
                        float(st.session_state.employee_pension) if st.session_state.status == "Inside IR35" else 0.0,
                        st.session_state.student_loan if st.session_state.status == "Inside IR35" else "None",
                        st.session_state.status,
                        st.session_state.vat_registered if st.session_state.status == "Outside IR35" else False
                    )
                    
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
                    st.error(f"Calculation error: {str(e)}")

    # Results Display
    if st.session_state.get('results'):
        st.subheader("Results")
        
        st.write("### Rate Summary")
        cols = st.columns(3)
        cols[0].metric("Client Rate", f"£{round(st.session_state.client_rate)}")
        cols[1].metric("Base Rate", f"£{round(st.session_state.base_rate)}")
        cols[2].metric("Pay Rate", f"£{round(st.session_state.pay_rate)}")
        
        st.write("### Margin Information")
        margin_data = [
            ["Margin Percentage", f"{st.session_state.margin['Margin Percentage']}%"],
            ["Daily Margin", f"£{st.session_state.margin['Daily Margin']}"],
            ["Total Margin", f"£{st.session_state.margin['Total Margin']}"]
        ]
        st.dataframe(styled_dataframe(pd.DataFrame(margin_data, columns=["Metric", "Value"])), use_container_width=True)
        
        if st.session_state.status == "Outside IR35":
            st.write("### Project Summary")
            summary_data = [
                ["Working Days", st.session_state.working_days],
                ["Project Total", f"£{round(st.session_state.results.get('Project Total', 0))}"]
            ]
            if st.session_state.vat_registered:
                summary_data.append(["VAT Charged to Client (20%)", f"£{round(st.session_state.results.get('VAT Amount', 0))}"])
            st.dataframe(styled_dataframe(pd.DataFrame(summary_data, columns=["Metric", "Value"])), use_container_width=True)
            st.warning(st.session_state.results.get('Disclaimer', ""))
        else:
            if st.session_state.employer_deductions:
                st.write("### Employer Deductions")
                deductions_data = [
                    ["Daily Employer NI (15%)", f"£{st.session_state.employer_deductions['Daily Employer NI']}"],
                    ["Daily Employer Pension", f"£{st.session_state.employer_deductions['Daily Employer Pension']}"],
                    ["Daily Apprentice Levy (0.5%)", f"£{st.session_state.employer_deductions['Daily Apprentice Levy']}"],
                    ["Total Employer NI", f"£{st.session_state.employer_deductions['Total Employer NI']}"],
                    ["Total Employer Pension", f"£{st.session_state.employer_deductions['Total Employer Pension']}"],
                    ["Total Apprentice Levy", f"£{st.session_state.employer_deductions['Total Apprentice Levy']}"],
                    ["Total Employer Deductions", f"£{st.session_state.employer_deductions['Total Employer Deductions']}"]
                ]
                st.dataframe(styled_dataframe(pd.DataFrame(deductions_data, columns=["Deduction", "Amount"])), use_container_width=True)
            
            st.write("### Project Breakdown")
            breakdown_data = [
                ["Daily Rates", f"£{round(st.session_state.pay_rate)}", f"£{round(st.session_state.results['Net Take-Home Pay'] / st.session_state.working_days)}"],
                ["Monthly Rates (20 days)", f"£{round(st.session_state.pay_rate * 20)}", f"£{round((st.session_state.results['Net Take-Home Pay'] / st.session_state.working_days) * 20)}"],
                [f"Project Total ({st.session_state.working_days} days)", f"£{round(st.session_state.pay_rate * st.session_state.working_days)}", f"£{round(st.session_state.results['Net Take-Home Pay'])}"]
            ]
            st.dataframe(styled_dataframe(pd.DataFrame(breakdown_data, columns=["Period", "Gross", "Net"])), use_container_width=True)
            
            basic_rate, holiday_pay = calculate_holiday_components(st.session_state.pay_rate)
            st.write("### Payslip Breakdown (Compliance)")
            st.dataframe(styled_dataframe(pd.DataFrame([
                ["Basic Daily Rate (excl. holiday pay)", f"£{basic_rate}"],
                ["Holiday Pay (per day)", f"£{holiday_pay}"]
            ], columns=["Component", "Amount"])), use_container_width=True)
            
            st.write("### Detailed Breakdown")
            breakdown_items = []
            for key, value in st.session_state.results.items():
                if key not in ["VAT Amount", "Working Days", "Disclaimer"]:
                    breakdown_items.append([key.replace("_", " ").title(), f"£{value}"])
            st.dataframe(styled_dataframe(pd.DataFrame(breakdown_items, columns=["Item", "Amount"])), use_container_width=True)
        
        # PDF Generation
        st.markdown("---")
        if st.button("📄 Generate PDF Report"):
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
                "💾 Download PDF",
                data=pdf_data,
                file_name=f"IR35_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )

    # Comparison Mode
    st.subheader("Comparison Mode")
    st.session_state.compare_mode = st.checkbox("Enable Comparison Mode")
    
    if st.session_state.compare_mode:
        st.info("""
        **Comparison Explanation**: 
        - **Inside IR35**: Pay Rate is after employer deductions
        - **Outside IR35**: Pay Rate equals Base Rate (no deductions)
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Inside IR35 Scenario**")
            inside_pay_rate = st.number_input(
                "Pay Rate (£)", 
                value=400.0,
                step=50.0,
                key="inside_pay_rate",
                help="Your take-home pay rate under IR35"
            )
        
        with col2:
            st.write("**Outside IR35 Scenario**")
            outside_base_rate = st.number_input(
                "Base Rate (£)", 
                value=500.0,
                step=50.0,
                key="outside_base_rate",
                help="Your equivalent rate as self-employed"
            )
            outside_vat = st.checkbox(
                "VAT Registered?", 
                value=False,
                key="outside_vat",
                help="Check if VAT registered (Outside IR35 only)"
            )
        
        if st.button("Compare Scenarios"):
            try:
                working_days = calculate_working_days(
                    st.session_state.start_date,
                    st.session_state.end_date,
                    st.session_state.days_per_week,
                    bank_holidays
                )
                
                # Inside scenario
                inside_base_rate = calculate_base_rate_from_pay(inside_pay_rate, "Inside IR35")
                inside_client_rate = calculate_client_rate(
                    inside_base_rate,
                    st.session_state.margin_percent
                )
                inside_result = ir35_tax_calculator(
                    inside_pay_rate, 
                    working_days, 
                    st.session_state.employee_pension,
                    st.session_state.student_loan,
                    "Inside IR35"
                )
                
                # Outside scenario
                outside_client_rate = calculate_client_rate(
                    outside_base_rate,
                    st.session_state.margin_percent
                )
                outside_result = ir35_tax_calculator(
                    outside_base_rate,
                    working_days,
                    0.0,
                    "None",
                    "Outside IR35",
                    outside_vat
                )
                
                # Display comparison
                comparison_data = [
                    ["Daily Rate", f"£{round(inside_pay_rate)}", f"£{round(outside_base_rate)}"],
                    ["Monthly Rate (20 days)", f"£{round(inside_pay_rate * 20)}", f"£{round(outside_base_rate * 20)}"],
                    ["Project Total", f"£{round(inside_result['Net Take-Home Pay'])}", f"£{round(outside_result['Project Total'])}"],
                    ["Effective Daily Rate (Net)", f"£{round(inside_result['Net Take-Home Pay'] / working_days)}", f"£{round(outside_result['Project Total'] / working_days)}"]
                ]
                
                if outside_vat:
                    comparison_data.append(["VAT Charged to Client", "N/A", f"£{round(outside_result['VAT Amount'])}"])
                
                st.dataframe(styled_dataframe(
                    pd.DataFrame(comparison_data, columns=["Metric", "Inside IR35", "Outside IR35"])
                ), use_container_width=True)
                
                # Manual copy option
                copy_text = "Metric\tInside IR35\tOutside IR35\n"
                for row in comparison_data:
                    copy_text += f"{row[0]}\t{row[1]}\t{row[2]}\n"
                st.text_area("Copy these results manually:", copy_text, height=150)
                
            except Exception as e:
                st.error(f"Comparison error: {str(e)}")

if __name__ == "__main__":
    main()
