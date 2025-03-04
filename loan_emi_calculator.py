from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import io
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/calculate-emi', methods=['POST'])
def calculate_emi():
    data = request.json
    
    principal = float(data.get('principal', 0))
    interest_rate = float(data.get('interest_rate', 0)) / 100 / 12  # Monthly interest rate
    tenure = int(data.get('tenure', 0))  # Tenure in months
    custom_emi = float(data.get('custom_emi', 0))
    start_date_str = data.get('start_date', datetime.today().strftime('%Y-%m-%d'))
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD"}), 400
    
    # Additional payments (if any)
    additional_payments = data.get('additional_payments', {})
    
    # Calculate default EMI
    default_emi = (principal * interest_rate * (1 + interest_rate) ** tenure) / ((1 + interest_rate) ** tenure - 1)
    
    # Use custom EMI if provided and greater than or equal to interest component
    min_emi = principal * interest_rate
    if custom_emi > 0:
        if custom_emi < min_emi:
            return jsonify({"error": f"Custom EMI must be at least {min_emi:.2f} to cover interest"}), 400
        emi = custom_emi
    else:
        emi = default_emi
    
    # Calculate amortization schedule
    schedule = []
    remaining_principal = principal
    total_months = 0
    month_date = start_date
    
    while remaining_principal > 0 and total_months < 360:  # Limit to 30 years to prevent infinite loops
        total_months += 1
        month_str = month_date.strftime('%Y-%m-%d')
        
        # Calculate interest for the month
        interest_payment = remaining_principal * interest_rate
        
        # Get additional payment for this month (if any)
        additional_payment = float(additional_payments.get(month_str, 0))
        
        # Calculate principal payment
        if emi + additional_payment > remaining_principal + interest_payment:
            # Last payment
            principal_payment = remaining_principal
            emi_this_month = principal_payment + interest_payment
            additional_payment = 0  # No need for additional payment
        else:
            principal_payment = emi - interest_payment + additional_payment
            emi_this_month = emi + additional_payment
        
        remaining_principal -= principal_payment
        
        # Ensure we don't go negative due to rounding errors
        if remaining_principal < 0:
            remaining_principal = 0
        
        month_data = {
            "month": total_months,
            "date": month_str,
            "emi": emi_this_month,
            "principal": principal_payment,
            "interest": interest_payment,
            "additional_payment": additional_payment,
            "balance": remaining_principal
        }
        
        schedule.append(month_data)
        
        # Move to next month
        month_date = add_one_month(month_date)
    
    response_data = {
        "default_emi": default_emi,
        "actual_emi": emi,
        "total_months": total_months,
        "total_interest": sum(month["interest"] for month in schedule),
        "total_payment": sum(month["emi"] for month in schedule),
        "schedule": schedule
    }
    
    return jsonify(response_data)

@app.route('/download-schedule', methods=['POST'])
def download_schedule():
    data = request.json
    schedule = data.get('schedule', [])
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(schedule)
    
    # Create a buffer
    buffer = io.BytesIO()
    
    # Write to Excel
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    
    # Return the file
    return send_file(
        buffer,
        as_attachment=True,
        download_name="amortization_schedule.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def add_one_month(date):
    """Add one month to the date."""
    month = date.month
    year = date.year + month // 12
    month = month % 12 + 1
    day = min(date.day, calendar.monthrange(year, month)[1])
    return date.replace(year=year, month=month, day=day)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
