import streamlit as st
from datetime import datetime, timedelta
import requests
import numpy as np
from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR

# ----------------------------
# Bank Holidays Utility
# ----------------------------
def get_uk_bank_holidays():
    try:
        response = requests.get("https://www.gov.uk/bank-holidays.json")
        response.raise_for_status()
        holidays = response.json()["england-and-wales"]["events"]
        return set(datetime.strptime(h["date"], "%Y-%m-%d").date() for h in holidays)
    except:
        return set()

# ----------------------------
# Workday Calculator
# ----------------------------
def calculate_workdays(start_date, end_date, days_per_week, holidays):
    weekdays = [MO, TU, WE, TH, FR][:days_per_week]
    all_days = list(rrule(DAILY, dtstart=start_date, until=end_date, byweekday=weekdays))
    working_days = [d for d in all_days if d.date() not in holidays]
    return len(working_days)

# ----------------------------
# Calculation Engine
# ----------------------------
def calculate_all_rates(entry_type, input_rate, margin_percent, 
                        employer_pension_percent, apprentice_levy_percent,
                        pension_contribution_percent, student_loan_plan,
                        status, work_days):

    margin_rate = margin_percent / 100
    apprentice_levy_rate = apprentice_levy_percent / 100
    employer_ni_rate = 0.15  # flat 15%
    inside_ir35 = status == "Inside IR35"

    # Calculate from base input
    if entry_type == "Client Rate":
        client_rate = input_rate
        base_rate = client_rate * (1 - margin_rate)
    elif entry_type == "Base Rate":
        base_rate = input_rate
        client_rate = base_rate / (1 - margin_rate)
    elif entry_type == "Pay Rate":
        if inside_ir35:
            gross_up_factor = 1 - (employer_ni_rate + apprentice_levy_rate + employer_pension_percent / 100)
            base_rate = input_rate / gross_up_factor
        else:
            base_rate = input_rate
        client_rate = base_rate / (1 - margin_rate)
    else:
        st.error("Invalid rate type")
        return {}

    # Employer deductions
    if inside_ir35:
        employer_ni = base_rate * employer_ni_rate
        apprentice_levy = base_rate * apprentice_levy_rate
        employer_pension = base_rate * (employer_pension_percent / 100)
    else:
        employer_ni = 0
        apprentice_levy = 0
        employer_pension = 0

    pay_rate = base_rate - employer_ni - apprentice_levy - employer_pension

    # Employee deductions
    annual_income = pay_rate * work_days
    personal_allowance = 12570
    basic_rate_threshold = 50270
    higher_rate_threshold = 125140

    basic_rate = 0.2
    higher_rate = 0.4
    additional_rate = 0.45

    if annual_income <= personal_allowance:
        income_tax = 0
    elif annual_income <= basic_rate_threshold:
        income_tax = (annual_income - personal_allowance) * basic_rate
    elif annual_income <= higher_rate_threshold:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate +
                      (annual_income - basic_rate_threshold) * higher_rate)
    else:
        income_tax = ((basic_rate_threshold - personal_allowance) * basic_rate +
                      (higher_rate_threshold - basic_rate_threshold) * higher_rate +
                      (annual_income - higher_rate_threshold) * additional_rate)

    ni_threshold = 12570
    if annual_income <= ni_threshold:
        employee_ni = 0
    elif annual_income <= basic_rate_threshold:
        employee_ni = (annual_income - ni_threshold) * 0.08
    else:
        employee_ni = ((basic_rate_threshold - ni_threshold) * 0.08 +
                       (annual_income - basic_rate_threshold) * 0.02)

    if student_loan_plan == "Plan 1" and annual_income > 22015:
        student_loan = (annual_income - 22015) * 0.09
    elif student_loan_plan == "Plan 2" and annual_income > 27295:
        student_loan = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Plan 4" and annual_income > 31395:
        student_loan = (annual_income - 31395) * 0.09
    elif student_loan_plan == "Plan 5" and annual_income > 27295:
        student_loan = (annual_income - 27295) * 0.09
    elif student_loan_plan == "Postgraduate Loan" and annual_income > 21000:
        student_loan = (annual_income - 21000) * 0.06
    else:
        student_loan = 0

    employee_pension = annual_income * (pension_contribution_percent / 100)
    net_income = annual_income - income_tax - employee_ni - student_loan - employee_pension

    def to_monthly(value):
        return value * 20  # Approximate monthly (20 working days)

    def to_total(value):
        return value * work_days

    return {
        "Client Rate": client_rate,
        "Base Rate": base_rate,
        "Pay Rate": pay_rate,
        "Net Daily": net_income / work_days,
        "Net Monthly": to_monthly(net_income / work_days),
        "Net Total": net_income,
        "Gross Daily": annual_income / work_days,
        "Gross Monthly": to_monthly(annual_income / work_days),
        "Gross Total": annual_income
    }

# ----------------------------
# Streamlit UI
# ----------------------------
st.title("IR35 Tax Calculator with Enhanced Logic")

entry_type = st.selectbox("Which Rate Are You Starting With?", ["Client Rate", "Base Rate", "Pay Rate"])
input_rate = st.number_input("Enter the value for selected rate (£)", min_value=0.0, step=50.0)

margin_percent = st.slider("Company Margin (%)", 0, 100, 10)
employer_pension_percent = st.slider("Employer Pension (%)", 0, 100, 3)
apprentice_levy_percent = st.slider("Apprentice Levy (%)", 0, 100, 0.5)
pension_contribution_percent = st.slider("Employee Pension (%)", 0, 100, 0)
student_loan_plan = st.selectbox("Student Loan Plan", ["None", "Plan 1", "Plan 2", "Plan 4", "Plan 5", "Postgraduate Loan"])
status = st.radio("IR35 Status", ["Inside IR35", "Outside IR35"])

start_date = st.date_input("Project Start Date", value=datetime.today())
end_date = st.date_input("Project End Date", value=datetime.today() + timedelta(days=60))
days_per_week = st.selectbox("How many days per week will you work?", [1, 2, 3, 4, 5])

if st.button("Calculate"):
    if start_date > end_date:
        st.error("Start date must be before end date.")
    else:
        holidays = get_uk_bank_holidays()
        work_days = calculate_workdays(start_date, end_date, days_per_week, holidays)
        results = calculate_all_rates(entry_type, input_rate, margin_percent, 
                                      employer_pension_percent, apprentice_levy_percent,
                                      pension_contribution_percent, student_loan_plan,
                                      status, work_days)

        if results:
            st.success(f"Total Workdays: {work_days}")
            for label, val in results.items():
                st.write(f"**{label}:** £{val:,.2f}")
