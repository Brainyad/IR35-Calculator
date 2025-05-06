import streamlit as st
from PIL import Image
from fpdf import FPDF
import requests
from datetime import datetime, timedelta

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
        holidays = data['england-and-wales']['events']
        return [datetime.strptime(event['date'], '%Y-%m-%d').date() for event in holidays]
    except:
        return [
            datetime(2023, 1, 2).date(), datetime(2023, 4, 7).date(), 
            datetime(2023, 4, 10).date(), datetime(2023, 5, 1).date(),
            datetime(2023, 5, 8).date(), datetime(2023, 5, 29).date(),
            datetime(2023, 8, 28).date(), datetime(2023, 12, 25).date(),
            datetime(2023, 12, 26).date()
        ]

# Calculate working days excluding weekends and bank holidays
def calculate_working_days(start_date, end_date, days_per_week, bank_holidays):
    if start_date >= end_date:
        return 0
    total_days = (end_date - start_date).days + 1
    working_days = sum(
        1 for day in range(total_days)
        if (start_date + timedelta(days=day)).weekday() < 5 and 
        (start_date + timedelta(days=day)) not in bank_holidays
    )
    full_weeks = working_days // 5
    remaining_days = working_days % 5
    return (full_weeks * days_per_week) + min(remaining_days, days_per_week)

# Helper functions for various calculations
def calculate_base_rate(client_rate, margin_percent):
    return client_rate * (1 - margin_percent / 100)

def calculate_client_rate(base_rate, margin_percent):
    return base_rate / (1 - margin_percent / 100)

def calculate_pay_rate(base_rate):
    return base_rate / 1.185  # 18.5% deductions

def calculate_base_rate_from_pay(pay_rate):
    return pay_rate * 1.185

def calculate_employer_deductions(base_rate, working_days):
    ni = base_rate * 0.15
    pension = base_rate * 0.03
    levy = base_rate * 0.005
    return {
        "Daily Employer NI": round(ni),
        "Daily Employer Pension": round(pension),
        "Daily Apprentice Levy": round(levy),
        "Total Employer NI": round(ni * working_days),
        "Total Employer Pension": round(pension * working_days),
        "Total Apprentice Levy": round(levy * working_days),
        "Total Employer Deductions": round((ni + pension + levy) * working_days)
    }

def calculate_margin(client_rate, base_rate, working_days):
    daily_margin = client_rate - base_rate
    total_margin = daily_margin * working_days
    margin_percent = ((client_rate - base_rate) / client_rate) * 100
    return {
        "Daily Margin": round(daily_margin),
        "Total Margin": round(total_margin),
        "Margin Percentage": round(margin_percent, 1)
    }
    # Tax calculator for IR35 compliance
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
            "Daily Rate": pay_rate,
            "Disclaimer": "As a self-employed consultant, you are responsible for calculating and paying your own taxes and National Insurance via Self Assessment. These figures show gross amounts and do not account for expenses or tax deductions."
        }
    else:
        annual_income = pay_rate * working_days
        personal_allowance = 12570
        basic_rate_threshold = 50270
        higher_rate_threshold = 125140
        basic_rate = 0.2
        higher_rate = 0.4
        additional_rate = 0.45
        ni_threshold = 12570
        ni_lower = 0.08
        ni_upper = 0.02
        employee_pension = annual_income * (pension_contribution_percent / 100)
        taxable_income = annual_income - employee_pension
        if taxable_income <= personal_allowance:
            income_tax = 0
        elif taxable_income <= basic_rate_threshold:
            income_tax = (taxable_income - personal_allowance) * basic_rate
        elif taxable_income <= higher_rate_threshold:
            income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((taxable_income - basic_rate_threshold) * higher_rate)
        else:
            income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate) + ((higher_rate_threshold - basic_rate_threshold) * higher_rate) + ((taxable_income - higher_rate_threshold) * additional_rate)
        ni_contribution = 0
        if annual_income > ni_threshold:
            if annual_income <= basic_rate_threshold:
                ni_contribution = (annual_income - ni_threshold) * ni_lower
            else:
                ni_contribution = ((basic_rate_threshold - ni_threshold) * ni_lower) + ((annual_income - basic_rate_threshold) * ni_upper)
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

# Streamlit UI Setup
st.set_page_config(page_title="IR35 Tax Calculator", layout="wide")

# Display company logo
try:
    logo = Image.open("B2e Logo.png")
    st.image(logo, width=200)
except:
    pass

st.title("IR35 Tax Calculator")

# Fetch UK bank holidays
bank_holidays = get_uk_bank_holidays()

# Configurations
col1, col2 = st.columns(2)
with col1:
    st.session_state.status = st.radio(
        "IR35 Status",
        ["Inside IR35", "Outside IR35"],
        index=0 if st.session_state.status == "Inside IR35" else 1,
        horizontal=True,
        key="status_config"
    )
with col2:
    st.session_state.calculation_mode = st.radio(
        "Start Calculation From:",
        ["Client Rate", "Base Rate", "Pay Rate"],
        index=["Client Rate", "Base Rate", "Pay Rate"].index(st.session_state.calculation_mode),
        horizontal=True,
        key="calculation_mode_config"
    )

# Input Form
with st.form("calculator_form"):
    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.calculation_mode == "Client Rate":
            st.session_state.client_rate = st.number_input(
                "Client Charge Rate (£):",
                min_value=0.0,
                value=float(st.session_state.client_rate),
                step=50.0,
                format="%.2f"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.margin_percent),
                step=0.5,
                format="%.1f"
            )
        elif st.session_state.calculation_mode == "Base Rate":
            st.session_state.base_rate = st.number_input(
                "Base Rate (£):",
                min_value=0.0,
                value=float(st.session_state.base_rate),
                step=50.0,
                format="%.2f"
            )
            st.session_state.margin_percent = st.number_input(
                "Margin (%):",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.margin_percent),
                step=0.5,
                format="%.1f"
            )
        else:  # Pay Rate
            st.session_state.pay_rate = st.number_input(
                "Pay Rate (£):",
                min_value=0.0,
                value=float(st.session_state.pay_rate),
                step=50.0,
                format="%.2f"
            )
# Submit Button
submitted = st.form_submit_button("Calculate")
if submitted:
    # Logic for calculation...
    pass
    with col2:
        # Additional inputs based on IR35 status
        if st.session_state.status == "Inside IR35":
            st.session_state.employee_pension = st.number_input(
                "Employee Pension Contribution (%):",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.employee_pension),
                step=0.5,
                format="%.1f"
            )
            st.session_state.student_loan = st.selectbox(
                "Student Loan Plan:",
                ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"],
                index=["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"].index(st.session_state.student_loan)
            )
        else:
            st.session_state.vat_registered = st.checkbox(
                "VAT Registered? (20%)",
                value=st.session_state.vat_registered
            )
        
        st.session_state.days_per_week = st.selectbox(
            "Days worked per week:",
            [1, 2, 3, 4, 5],
            index=st.session_state.days_per_week - 1
        )
        
        st.session_state.start_date = st.date_input(
            "Project Start Date:",
            value=st.session_state.start_date
        )
        
        st.session_state.end_date = st.date_input(
            "Project End Date:",
            value=st.session_state.end_date
        )

# Process calculation upon submission
if submitted:
    if st.session_state.start_date >= st.session_state.end_date:
        st.error("End date must be after the start date.")
    else:
        try:
            # Calculate working days
            st.session_state.working_days = calculate_working_days(
                st.session_state.start_date,
                st.session_state.end_date,
                st.session_state.days_per_week,
                bank_holidays
            )
            
            # Perform calculations based on IR35 status
            if st.session_state.status == "Inside IR35":
                if st.session_state.calculation_mode == "Client Rate":
                    st.session_state.base_rate = calculate_base_rate(
                        st.session_state.client_rate,
                        st.session_state.margin_percent
                    )
                    st.session_state.pay_rate = calculate_pay_rate(st.session_state.base_rate)
                elif st.session_state.calculation_mode == "Base Rate":
                    st.session_state.client_rate = calculate_client_rate(
                        st.session_state.base_rate,
                        st.session_state.margin_percent
                    )
                    st.session_state.pay_rate = calculate_pay_rate(st.session_state.base_rate)
                else:
                    st.session_state.base_rate = calculate_base_rate_from_pay(st.session_state.pay_rate)
                    st.session_state.client_rate = calculate_client_rate(
                        st.session_state.base_rate,
                        st.session_state.margin_percent
                    )
                
                # Calculate deductions and margins
                st.session_state.employer_deductions = calculate_employer_deductions(
                    st.session_state.base_rate,
                    st.session_state.working_days
                )
                st.session_state.margin = calculate_margin(
                    st.session_state.client_rate,
                    st.session_state.base_rate,
                    st.session_state.working_days
                )
            else:
                if st.session_state.calculation_mode == "Pay Rate":
                    st.session_state.base_rate = st.session_state.pay_rate
            
            # Final tax calculation
            st.session_state.results = ir35_tax_calculator(
                st.session_state.pay_rate,
                st.session_state.working_days,
                st.session_state.employee_pension if st.session_state.status == "Inside IR35" else 0.0,
                st.session_state.student_loan if st.session_state.status == "Inside IR35" else "None",
                st.session_state.status,
                st.session_state.vat_registered if st.session_state.status == "Outside IR35" else False
            )
        
        except Exception as e:
            st.error(f"An error occurred during the calculation: {str(e)}")

# Display results if available
if st.session_state.get('results'):
    st.subheader("Results")
    
    if st.session_state.status == "Outside IR35":
        st.write("## Outside IR35 - Self-Employed Consultant")
        st.write(f"**Base Rate = Pay Rate:** £{round(st.session_state.pay_rate)}")
        st.write(f"**Working Days:** {st.session_state.results['Working Days']}")
        st.write(f"**Project Total:** £{round(st.session_state.results['Project Total'])}")
        if st.session_state.results['VAT Amount'] > 0:
            st.write(f"**VAT Charged to Client (20%):** £{round(st.session_state.results['VAT Amount'])}")
        st.warning(st.session_state.results['Disclaimer'])
    else:
        st.write("## Inside IR35 - PAYE Employee")
        st.write(f"**Client Rate:** £{round(st.session_state.client_rate)}")
        st.write(f"**Base Rate:** £{round(st.session_state.base_rate)}")
        st.write(f"**Pay Rate:** £{round(st.session_state.pay_rate)}")
        st.write(f"**Working Days:** {st.session_state.results['Working Days']}")
        st.write(f"**Net Take-Home Pay:** £{round(st.session_state.results['Net Take-Home Pay'])}")    
        st.write("### Employer Deductions")
        if st.session_state.employer_deductions:
            st.write(f"**Daily NI (15%):** £{st.session_state.employer_deductions['Daily Employer NI']}")
            st.write(f"**Daily Pension (3%):** £{st.session_state.employer_deductions['Daily Employer Pension']}")
            st.write(f"**Daily Levy (0.5%):** £{st.session_state.employer_deductions['Daily Apprentice Levy']}")
            st.write(f"**Total NI:** £{st.session_state.employer_deductions['Total Employer NI']}")
            st.write(f"**Total Pension:** £{st.session_state.employer_deductions['Total Employer Pension']}")
            st.write(f"**Total Levy:** £{st.session_state.employer_deductions['Total Apprentice Levy']}")
            st.write(f"**Total Employer Deductions:** £{st.session_state.employer_deductions['Total Employer Deductions']}")

        st.write("### Margin")
        if st.session_state.margin:
            st.write(f"**Margin Percentage:** {st.session_state.margin['Margin Percentage']}%")
            st.write(f"**Daily Margin:** £{st.session_state.margin['Daily Margin']}")
            st.write(f"**Total Margin:** £{st.session_state.margin['Total Margin']}")

        st.write("### Take-Home Pay")
        st.write(f"**Net Take-Home Pay:** £{round(st.session_state.results['Net Take-Home Pay'])}")
        st.write(f"**Gross Income:** £{round(st.session_state.results['Gross Income'])}")
        st.write(f"**Income Tax:** £{round(st.session_state.results['Income Tax'])}")
        st.write(f"**Employee NI:** £{round(st.session_state.results['Employee NI'])}")
        st.write(f"**Employee Pension Contributions:** £{round(st.session_state.results['Employee Pension'])}")
        if st.session_state.results.get('Student Loan Repayment', 0) > 0:
            st.write(f"**Student Loan Repayment:** £{round(st.session_state.results['Student Loan Repayment'])}")

    # Option to download results as PDF
    if st.button("Generate PDF Report"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Title and Summary
        pdf.set_font("Arial", size=16, style="B")
        pdf.cell(200, 10, "IR35 Tax Calculation Results", ln=True, align="C")
        pdf.ln(10)

        # Add Results
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 8, "Summary", ln=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(200, 8, f"Client Rate: £{round(st.session_state.client_rate)}", ln=True)
        pdf.cell(200, 8, f"Base Rate: £{round(st.session_state.base_rate)}", ln=True)
        pdf.cell(200, 8, f"Pay Rate: £{round(st.session_state.pay_rate)}", ln=True)
        pdf.cell(200, 8, f"Working Days: {st.session_state.results['Working Days']}", ln=True)
        pdf.cell(200, 8, f"Net Take-Home Pay: £{round(st.session_state.results['Net Take-Home Pay'])}", ln=True)

        # Employer Deductions
        if st.session_state.status == "Inside IR35" and st.session_state.employer_deductions:
            pdf.ln(10)
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 8, "Employer Deductions", ln=True)
            pdf.set_font("Arial", size=11)
            pdf.cell(200, 8, f"Daily NI: £{st.session_state.employer_deductions['Daily Employer NI']}", ln=True)
            pdf.cell(200, 8, f"Daily Pension: £{st.session_state.employer_deductions['Daily Employer Pension']}", ln=True)
            pdf.cell(200, 8, f"Daily Levy: £{st.session_state.employer_deductions['Daily Apprentice Levy']}", ln=True)
            pdf.cell(200, 8, f"Total NI: £{st.session_state.employer_deductions['Total Employer NI']}", ln=True)
            pdf.cell(200, 8, f"Total Pension: £{st.session_state.employer_deductions['Total Employer Pension']}", ln=True)
            pdf.cell(200, 8, f"Total Levy: £{st.session_state.employer_deductions['Total Apprentice Levy']}", ln=True)

        # Save and provide download link
        pdf_output = pdf.output(dest="S").encode("latin1")
        st.download_button(
            "Download Report",
            data=pdf_output,
            file_name="IR35_Tax_Report.pdf",
            mime="application/pdf"
        )
      # Comparison Mode for Inside and Outside IR35
st.subheader("Comparison Mode")
st.session_state.compare_mode = st.checkbox("Enable Comparison Mode", value=st.session_state.compare_mode)

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
            "Pay Rate (£):",
            min_value=0.0,
            value=400.0,
            step=50.0,
            format="%.2f",
            key="inside_pay_rate"
        )
    with col2:
        st.write("**Scenario 2 - Outside IR35**")
        outside_base_rate = st.number_input(
            "Base Rate (£):",
            min_value=0.0,
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
            inside_pay_rate,
            working_days,
            st.session_state.employee_pension,
            st.session_state.student_loan,
            "Inside IR35",
            False
        )

        # Outside IR35 scenario
        outside_result = ir35_tax_calculator(
            outside_base_rate,
            working_days,
            0.0,
            "None",
            "Outside IR35",
            outside_vat
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
            st.write(f"**Daily Net:** £{round(inside_result['Net Take-Home Pay'] / working_days)}")
            st.write(f"**Project Net:** £{round(inside_result['Net Take-Home Pay'])}")

        with col2:
            st.write("### Outside IR35")
            st.write(f"**Base Rate = Pay Rate:** £{round(outside_base_rate)}")
            if outside_vat:
                st.write(f"**VAT Charged to Client (20%):** £{round(outside_result['VAT Amount'])}")
            st.write(f"**Project Total:** £{round(outside_result['Project Total'])}")
            st.warning("Self-employed consultants must calculate their own taxes.")

        # Difference Calculation
        difference = outside_result['Project Total'] - inside_result['Net Take-Home Pay']
        st.write(f"**Gross Difference (Outside - Inside):** £{round(difference)}")  
# Footer information
st.markdown("---")
st.markdown(
    """
    **Disclaimer**: This calculator is a guide and does not constitute professional financial advice.
    Always consult with a qualified accountant or tax advisor for your specific situation.
    """
)

st.markdown(
    """
    **About**: This tool has been provided to help contractors and freelancers estimate their earnings and deductions under the IR35 rules.
    """
)

st.markdown(
    """
    **Contact**: For any issues or suggestions, please contact the developer at [support@example.com](mailto:support@example.com).
    """
)
