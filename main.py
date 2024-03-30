from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from pymongo import MongoClient
from bson.json_util import dumps
from datetime import datetime, timedelta
import json
from bson.objectid import ObjectId
import calendar
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import io
from datetime import datetime
import os
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_here'
# Replace 'your_connection_string' with your actual MongoDB connection string
client = MongoClient('mongodb+srv://aayush:Aayush12@cluster0.yoesoft.mongodb.net/')
db = client["BOM-Data"]
collection = db["Batch_sheet"]
new_data_collection = db["Base_data"]  # The new collection for the submitted data
base_data_collection = db['Base_data_transaction']
raw_material_db = db["List_of_raw_materials"]
inward_db = db["inward"]
production_db = db["Production_sheet"]
fg_rm_db = db["FG-RW"]
production_transaction_db = db['production_transaction']
city_db = db['city']
dispatch_db = db['dispatch']
net_inventory_granules_db = db['net_inventory_granules']
net_inventory_liquid_db = db['net_inventory_liquid']
net_inventory_mapping_liquids = db['net_inventory_mapping_liquids']

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('home_page.html')


@app.route('/batch_sheet', methods=['GET', 'POST'])
def batch_sheet():
    if request.method == 'POST':
        # This is the value selected by the user
        qty_pieces = request.form.get('qty_pieces')
        product_info = collection.find_one({'Qty (pieces)': qty_pieces})
        return render_template('batch_sheet.html', product_info=product_info)

    # Fetch the list of available 'Qty (pieces)' for the dropdown
    qty_options = collection.distinct('Qty (pieces)')
    # Set initial product info to None so that the table is initially empty
    return render_template('batch_sheet.html', qty_options=qty_options, product_info=None)

@app.route('/fetch_product_info', methods=['POST'])
def fetch_product_info():
    qty_pieces = request.json['qty_pieces']
    product_info = collection.find_one({'Qty (pieces)': qty_pieces}, {'_id': 0})

    return jsonify(product_info)



@app.route('/submit_data_batch_sheet', methods=['POST'])
def submit_data_batch_sheet():
    batch_no = request.form['batch_no']
    qty_pieces = request.form['qty_pieces']
    mfg_date = request.form['mfg_date']
    qty_kgs_ltr = float(request.form['qty_kgs_ltr'])

    # Fetch product info from MongoDB
    product_info = collection.find_one({'Qty (pieces)': qty_pieces}, {'_id': 0})

    # Calculate Bucket / Label
    unit_kg = product_info.get('Unit (KG)', 1)  # Default to 1 to avoid division by zero
    bucket_label = qty_kgs_ltr / unit_kg

    # Calculate Box / Label
    qty_in_one_box = product_info.get('Qty in 1 box', 1)
    box_label = bucket_label / qty_in_one_box

    # Calculate Exp Date
    exp_year = product_info.get('Expiry Age', 0)
    mfg_date_obj = datetime.strptime(mfg_date, '%Y-%m-%d')
    exp_date_obj = mfg_date_obj.replace(year=mfg_date_obj.year + exp_year)
    exp_date = exp_date_obj.strftime('%Y-%m-%d')

    # Prepare data for insertion
    data_to_save = {
        "Batch No": batch_no,
        "Qty (pieces)": qty_pieces,
        "Mfg Date": mfg_date,
        "MRP per unit": product_info.get('MRP per unit', ''),
        "Qty (kgs / ltr)": qty_kgs_ltr,
        "Exp Date": exp_date,
        "USP kg / ltr basis": product_info.get('USP kg / ltr basis', ''),
        "Bucket / Label": str(bucket_label),
        "Mono Cartons": '',  # Set as per your logic
        "Box Label": str(box_label),
        "MRP per box": product_info.get('MRP per box', '')
    }

    # Insert the data into the collections
    new_data_collection.insert_one(data_to_save)
    base_data_collection.insert_one(data_to_save)

    return redirect(url_for('index'))

@app.route('/view_base_data', methods=['GET'])
def view_base_data():
    entries = base_data_collection.find()

    return render_template('view_base_data.html', entries=entries)

@app.route('/delete_base_data/<id>', methods=['POST'])
def delete_base_data(id):
    base_data_collection.delete_one({'_id': ObjectId(id)})
    new_data_collection.delete_one({'_id': ObjectId(id)})
    # ... (Perform additional deletions/rollbacks as required)
    return redirect(url_for('view_base_data'))

@app.route('/additional_info', methods=['GET', 'POST'])
def additional_info():
    if request.method == 'POST':
        data = request.form.to_dict()
        pdf = generate_pdf(data)
        return pdf
    else:
        batch_no = request.args.get('batch_no')
        return render_template('additional_info.html', batch_no=batch_no)

def generate_pdf(data):
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)

    # Add your PDF generation logic here
    # For example:
    c.drawString(100, 750, "Batch Number: " + data.get("batch_no", ""))
    c.drawString(100, 730, "Supplier B.No: " + data.get("supplier_b_no", ""))

    # Close the PDF object cleanly
    c.showPage()
    c.save()

    # PDF will be returned directly in the browser
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, filename = r'C:\Users\aaypatil\Desktop\BOM-ERP\Time-Traveller\Page1-8.pdf', mimetype='application/pdf')

# Sample data for date dropdown
date_options = {
    'Today': datetime.now().strftime('%Y-%m-%d'),
    'Yesterday': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
    'Day Before Yesterday': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
}

# Sample data for item dropdown (replace with your actual data from MongoDB)
item_options = raw_material_db.distinct("List of Raw Materials")

@app.route('/inward', methods=["GET","POST"])
def inward():
    return render_template('inward.html', date_options=date_options, item_options=item_options)

@app.route('/submit_inward', methods=['POST'])
def submit_inward():
    # Get form data
    date = request.form['date']
    item = request.form['item']
    qty = request.form['qty']
    vendor_name = request.form['vendor_name']
    truck_no = request.form['truck_no']
    batch_no = request.form['batch_no']
    invoice_challan_no = request.form.get('invoice_challan_no', '')  # Optional field
    entry_type = request.form['entry_type']
    if entry_type in ["Purchase return", "Wastage"]:

        qty = -1*int(qty)
    else:
        qty = int(qty)

    # Save form data to MongoDB
    inward_db.insert_one({
        'Date': date,
        'Item': item,
        'Qty': qty,
        'Vendor Name': vendor_name,
        'Truck No': truck_no,
        'Batch No': batch_no,
        'invoice_challan_no': invoice_challan_no,
        'Type of Entry': entry_type
    })
    return redirect(url_for('index'))

@app.route('/view_inward', methods=['GET'])
def view_inward():
    entries = inward_db.find()
    return render_template('view_inward.html', entries=entries)

@app.route('/delete_inward/<id>', methods=['POST'])
def delete_inward(id):
    # Perform deletion
    inward_db.delete_one({'_id': ObjectId(id)})
    # Implement undo logic here for associated collections
    # ...
    return redirect(url_for('view_inward'))


@app.route('/production_sheet', methods=["GET","POST"])
def production_sheet():
    unique_batch = new_data_collection.distinct("Batch No")
    unique_items = new_data_collection.distinct("Qty (pieces)")

    return render_template('production_sheet.html', unique_items=unique_items, unique_batch=unique_batch)

@app.route('/submit_production', methods=['POST'])
def submit_production():
    # Get form data
    date = request.form['date']
    item = request.form['item']
    qty_input = int(request.form['qty'])
    batch_no = request.form['batch_no']

    # Get Qty (kgs / ltr) from MongoDB for the selected item and batch number
    qty_db = int(new_data_collection.find_one({"Qty (pieces)": item, "Batch No": batch_no})["Qty (kgs / ltr)"])

    # Check if the input quantity is not greater than available quantity
    if qty_input > qty_db:
        return "Quantity input exceeds available quantity for this item."

    # Calculate updated quantity
    updated_qty = qty_db - qty_input

    # Update quantity in first database
    new_data_collection.update_one({"Qty (pieces)": item, "Batch No": batch_no}, {"$set": {"Qty (kgs / ltr)": updated_qty}})

    # Insert new entry in second database
    print("check   ", production_db.find_one({"Item": item, "Batch No": batch_no}))
    if production_db.find_one({"Item": item, "Batch No": batch_no}):
        doc = production_db.find_one({"Item": item, "Batch No": batch_no})
        production_db.update_one({"Item": item, "Batch No": batch_no}, {"$set": {"Qty": doc['Qty'] + qty_input}})
    else:
        production_db.insert_one({
            'Date': date,
            'Item': item,
            'Qty': qty_input,
            'Batch No': batch_no
        })
    production_transaction_db.insert_one(
        {
            'Date': date,
            'Item': item,
            'Qty': qty_input,
            'Batch No': batch_no
        }
    )
    raw_materials_data = fg_rm_db.find_one({"Particulars": item})

    # Calculate the quantities and save to another database
    for key, value in raw_materials_data.items():

        if key not in ['_id', 'Particulars', 'Unit (KG)', 'Unit (ML)', 'Qty in 1 box'] and isinstance(value, (int, float)) and value != 0:
            calculated_qty = -1 * value * int(qty_input)
            new_entry = {
                "Date": date,
                "Item": key,
                "Qty": calculated_qty,
                "Batch No": batch_no,
                "Type": "Production Debit"
            }
            inward_db.insert_one(new_entry)

    return redirect(url_for('index'))

@app.route('/view_production', methods=['GET'])
def view_production():
    entries = list(production_transaction_db.find())
    for entry in entries:
        entry['_id'] = str(entry['_id'])
    return render_template('view_production.html', entries=entries)

@app.route('/delete_production/<id>', methods=['POST'])
def delete_production(id):
    # Find the entry in the main database using the provided ID
    entry = production_transaction_db.find_one({'_id': ObjectId(id)})

    if entry is None:
        return "Entry not found", 404

    # Delete the entry from the main database (production_transaction_db)
    production_transaction_db.delete_one({'_id': ObjectId(id)})

    # Logic to delete corresponding entry from production_db
    # Assuming the 'Date', 'Item', and 'Batch No' uniquely identify an entry in production_db
    production_db.delete_one({
        'Date': entry['Date'],
        'Item': entry['Item'],
        'Batch No': entry['Batch No'],
        'Qty': entry['Qty']
    })
    item = entry['Item']
    date = entry['Date']
    batch_no = entry['Batch No']
    qty_input = entry['Qty']
    raw_materials_data = fg_rm_db.find_one({"Particulars": item})

    # Calculate the quantities and save to another database
    for key, value in raw_materials_data.items():

        if key not in ['_id', 'Particulars', 'Unit (KG)', 'Unit (ML)', 'Qty in 1 box'] and isinstance(value, (
        int, float)) and value != 0:
            calculated_qty = value * int(qty_input)
            new_entry = {
                "Date": date,
                "Item": key,
                "Qty": calculated_qty,
                "Batch No": batch_no,
                "Type": "Production Debit Reversa;"
            }
            inward_db.insert_one(new_entry)

    # Update the new_data_collection to reverse the Qty change
    new_data_collection.update_one(
        {"Batch No": entry['Batch No']},
        {"$inc": {"Qty (kgs / ltr)": entry['Qty']}}
    )

    # Redirect to the view_production page
    return redirect(url_for('view_production'))


@app.route('/get_batch_numbers', methods=["POST"])
def get_batch_numbers():
    # Get selected item from the request
    selected_item = request.json['selected_item']

    # Retrieve unique batch numbers for the selected item
    unique_batch = new_data_collection.distinct("Batch No", {"Qty (pieces)": selected_item})

    # Return the unique batch numbers as JSON
    return jsonify(unique_batch)

@app.route('/net_inventory_raw_material')
def net_inventory_raw_material():
    pipeline = [
        {"$group": {"_id": "$Item", "TotalQty": {"$sum": "$Qty"}}}
    ]
    results = inward_db.aggregate(pipeline)
    items = [{item['_id']: item['TotalQty']} for item in results]
    return render_template('net_inventory_raw_material.html', items=items)

@app.route('/dispatch', methods=['GET', 'POST'])
def dispatch():
    if request.method == 'POST':
        # Process form data and insert into MongoDB
        data = {
            'date': request.form['date'],
            'city': request.form['city'],
            'address': request.form.get('address'),  # Optional field
            'item': request.form['item'],
            'Batch No': request.form['batch_no'],
            'qty': int(request.form['qty'])
        }

        # Validate and update Qty
        item_doc = production_db.find_one({'Item': data['item']})
        print(data['qty'])
        print(item_doc['Qty'])
        if item_doc and data['qty'] <= item_doc['Qty']:
            dispatch_db.insert_one(data)  # Insert data into a new collection
            production_db.update_one({'Item': data['item']}, {'$inc': {'Qty': -data['qty']}})  # Update qty
            return redirect(url_for('index'))
        else:
            return 'Quantity is more than available', 400

    # Fetch data for dropdowns
    cities = [doc['Cities'] for doc in city_db.find()]  # Fetch city names from city_db

    items = [doc['Item'] for doc in production_db.find()]  # Fetch item names from production_db

    return render_template('dsipatch.html', cities=cities, items=items)

@app.route('/get_batch_numbers_for_dispatch', methods=["POST"])
def get_batch_numbers_for_dispatch():
    selected_item = request.json['selected_item']
    batch_numbers = production_db.distinct("Batch No", {"Item": selected_item})

    return jsonify(batch_numbers)

@app.route('/view_dispatch', methods=['GET'])
def view_dispatch():
    entries = list(dispatch_db.find())
    for entry in entries:
        entry['_id'] = str(entry['_id'])
    return render_template('view_dispatch.html', entries=entries)


@app.route('/delete_dispatch/<id>', methods=['POST'])
def delete_dispatch(id):
    # Perform deletion
    data = dispatch_db.find_one({'_id': ObjectId(id)})
    dispatch_db.delete_one({'_id': ObjectId(id)})

    production_db.update_one({'Item': data['item']}, {'$inc': {'Qty': data['qty']}})
    # Implement any necessary undo operations for associated collections
    # ...
    return redirect(url_for('view_dispatch'))

@app.route('/item_details/<item_name>')
def item_details(item_name):
    # Fetch all records for the selected item from inward_db
    item_records = inward_db.find({'Item': item_name})
    return render_template('item_details.html', item_records=item_records, item_name=item_name)

@app.route('/net_inventory_production')
def net_inventory_production():
    pipeline = [
        {"$group": {"_id": "$Item", "TotalQty": {"$sum": "$Qty"}}}
    ]
    results = production_db.aggregate(pipeline)
    items = [{item['_id']: item['TotalQty']} for item in results]
    return render_template('net_inventory_production.html', items=items)

@app.route('/open_batch')
def open_batch():
    pipeline = [
        {"$group": {"_id": "$Batch No", "TotalQty": {"$sum": "$Qty (kgs / ltr)"}}}
    ]
    results = new_data_collection.aggregate(pipeline)
    batches = [{batch['_id']: batch['TotalQty']} for batch in results]
    return render_template('open_batch.html', batches=batches)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/batch_details/<batch_no>')
def batch_details(batch_no):
    base_data = list(base_data_collection.find({"Batch No": batch_no}, {'_id': 0}))
    production_data = list(production_transaction_db.find({"Batch No": batch_no}, {'_id': 0}))

    # Combine data and set the 'Type'
    for entry in base_data:
        entry['Type'] = 'Batch-Data'
    for entry in production_data:
        entry['Type'] = 'Production-Data'
        # Rename fields to match those in base_data
        entry['Qty (pieces)'] = entry.pop('Item')
        entry['Mfg Date'] = entry.pop('Date')
        entry['Qty (kgs / ltr)'] = entry.pop('Qty')

    combined_data = base_data + production_data

    return render_template('batch_details.html', combined_data=combined_data)

@app.route('/item_details_finished_goods/<item_name>')
def item_details_finished_goods(item_name):
    production_data = list(production_transaction_db.find({"Item": item_name}, {'_id': 0}))
    dispatch_data = list(dispatch_db.find({"item": item_name}, {'_id': 0}))

    # Add a 'Type' field to distinguish the data
    for entry in production_data:
        entry['Type'] = 'Production-Data'
        entry['Mfg Date'] = entry.pop('Date')
        entry['Qty (kgs / ltr)'] = entry.pop('Qty')
    for entry in dispatch_data:
        entry['Type'] = 'Dispatch-Data'
        # Rename fields to match those in production_data
        entry['Batch No'] = entry.pop('Batch No')
        entry['Qty (pieces)'] = entry.pop('item')
        entry['Mfg Date'] = entry.pop('date')
        entry['Qty (kgs / ltr)'] = entry.pop('qty')

    combined_data = production_data + dispatch_data

    return render_template('item_details_finished_goods.html', combined_data=combined_data)

@app.route('/net_inventory_granules')
def net_inventory_granules():
    unique_granules = net_inventory_granules_db.distinct("Product Name")

    table_data = []

    for product_name in unique_granules:
        granules_data = net_inventory_granules_db.find_one({"Product Name": product_name}) or {}
        production_data = production_db.find_one({"Item": product_name}) or {}

        brand_name = granules_data.get('BRAND NAME', 'Unknown')
        pack_size = granules_data.get('Pack Size', 'Unknown')
        fg_per_kg = production_data.get('Qty', 0) * granules_data.get('FG PER KG', 0)
        print(production_data.get('Qty', 0), granules_data.get('BRAND NAME', 'Unknown'), " ",granules_data.get('FG PER KG', 0), fg_per_kg)
        fg_qty_per_mt = production_data.get('Qty', 0) / 1000 if production_data else 0
        fg_qty_per_pcs = production_data.get('Qty', 0) if production_data else 0

        table_data.append({
            "BRAND NAME": brand_name,
            "PRODUCT NAME": product_name,
            "PACK SIZE": pack_size,
            "FG QTY PER MT.": fg_qty_per_mt,
            "FG PER KG": fg_per_kg,
            "FG QTY PER PCS": fg_qty_per_pcs
        })
    return render_template('net_inventory_granules.html', table_data=table_data)

@app.route('/net_inventory_liquid')
def net_inventory_liquid():
    liquid_data = net_inventory_liquid_db.find()  # Assuming this retrieves all documents in the collection
    table_data = []

    for data in liquid_data:
        metric_name = data.get('Metric Name')
        no_of_case_brand_sl = data.get('No of Case')
        no_of_case_wilicon = data.get('No of Case')  # If different, fetch accordingly
        per_ltr_brand_sl = data.get('Per ltr')
        per_ltr_wilicon = data.get('Per ltr')  # If different, fetch accordingly
        brand_sl_name = data.get('BRAND SL ')
        wilicon_name = data.get('WILICON')

        # Get production quantities
        production_qty_brand_sl = production_db.find_one({"Item": brand_sl_name}, {'Qty': 1})
        production_qty_wilicon = production_db.find_one({"Item": wilicon_name}, {'Qty': 1})

        # Calculate figures based on the Qty from production_db, defaulting to 0 if not found

        brand_sl_per_ltr = production_qty_brand_sl['Qty'] * (  per_ltr_brand_sl/ 1000) if production_qty_brand_sl and per_ltr_brand_sl else 0
        brand_sl_cases = brand_sl_per_ltr / no_of_case_brand_sl if production_qty_brand_sl and no_of_case_brand_sl else 0
        wilicon_per_ltr = production_qty_wilicon['Qty'] * ( per_ltr_wilicon/ 1000) if production_qty_wilicon and per_ltr_wilicon else 0
        wilicon_cases = wilicon_per_ltr / no_of_case_wilicon if production_qty_wilicon and no_of_case_wilicon else 0
        table_data.append({
            "PACK SIZE": metric_name,
            "BRAND SL No.of Case": brand_sl_cases,
            "BRAND SL Per Ltr.": brand_sl_per_ltr,
            "WILICON No.of Case": wilicon_cases,
            "WILICON Per Ltr.": wilicon_per_ltr,
        })

    return render_template('net_inventory_liquid.html', table_data=table_data)


@app.route('/Annual_dispatch_report_granule', methods=['GET', 'POST'])
def Annual_dispatch_report_granule():
    current_year = datetime.now().year
    selected_year = request.form.get('year', str(current_year))

    # Fetch all pack sizes from net_inventory_granules_db
    pack_sizes_info = net_inventory_granules_db.find({}, {"Pack Size": 1, "Product Name": 1})

    # Initialize a dictionary to store pack sizes and their corresponding product names
    pack_sizes_products = {doc['Pack Size']: doc['Product Name'] for doc in pack_sizes_info}

    # Initialize report data structure
    report_data = []
    for month_index in range(1, 13):  # Loop through all months
        monthly_data = {}
        for pack_size, product_name in pack_sizes_products.items():
            start_date = datetime(int(selected_year), month_index, 1)
            end_date = datetime(int(selected_year), month_index,
                                calendar.monthrange(int(selected_year), month_index)[1])

            # Convert dates to strings that match the format stored in the dispatch_db
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            # Query the dispatch_db for total dispatched quantity for this product name
            total_dispatched = dispatch_db.aggregate([
                {
                    "$match": {
                        "item": product_name,
                        "date": {"$gte": start_date_str, "$lte": end_date_str}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "totalQty": {"$sum": "$qty"}
                    }
                }
            ])
            try:
                monthly_data[pack_size] = next(total_dispatched)['totalQty']
            except StopIteration:
                monthly_data[pack_size] = 0  # No data found for this month

        report_data.append(monthly_data)

    months = [datetime(2000, m, 1).strftime('%B') for m in range(1, 13)]

    return render_template('annual_dispatch_report_granule.html', years=range(2018, current_year + 1),
                           selected_year=selected_year, pack_sizes=pack_sizes_products.keys(), report_data=report_data,
                           months=months)

@app.route('/Annual_dispatch_report_liquid', methods=['GET', 'POST'])
def Annual_dispatch_report_liquid():
    current_year = datetime.now().year
    selected_year = request.form.get('year', str(current_year))

    # Fetch all pack sizes from net_inventory_granules_db
    pack_sizes_info = net_inventory_mapping_liquids.find({}, {"Pack Size": 1, "Product Name": 1})

    # Initialize a dictionary to store pack sizes and their corresponding product names
    pack_sizes_products = {doc['Pack Size']: doc['Product Name'] for doc in pack_sizes_info}

    # Initialize report data structure
    report_data = []
    for month_index in range(1, 13):  # Loop through all months
        monthly_data = {}
        for pack_size, product_name in pack_sizes_products.items():
            start_date = datetime(int(selected_year), month_index, 1)
            end_date = datetime(int(selected_year), month_index,
                                calendar.monthrange(int(selected_year), month_index)[1])

            # Convert dates to strings that match the format stored in the dispatch_db
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')

            # Query the dispatch_db for total dispatched quantity for this product name
            total_dispatched = dispatch_db.aggregate([
                {
                    "$match": {
                        "item": product_name,
                        "date": {"$gte": start_date_str, "$lte": end_date_str}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "totalQty": {"$sum": "$qty"}
                    }
                }
            ])
            try:
                monthly_data[pack_size] = next(total_dispatched)['totalQty']
            except StopIteration:
                monthly_data[pack_size] = 0  # No data found for this month

        report_data.append(monthly_data)

    months = [datetime(2000, m, 1).strftime('%B') for m in range(1, 13)]

    return render_template('annual_dispatch_report_liquid.html', years=range(2018, current_year + 1),
                           selected_year=selected_year, pack_sizes=pack_sizes_products.keys(), report_data=report_data,
                           months=months)

@app.route('/Monthly_dispatch_report_liquid', methods=['GET', 'POST'])
def monthly_dispatch_report_liquid():
    # Get current year and month
    current_year = datetime.now().year
    current_month = datetime.now().month

    # Handle form submission
    selected_year = request.form.get('year', current_year)
    selected_month = request.form.get('month', current_month)

    # Fetch unique product names from net_inventory_mapping_liquids_db
    product_names_info = net_inventory_mapping_liquids.distinct("Product Name")

    # Initialize report data structure
    days_in_month = calendar.monthrange(int(selected_year), int(selected_month))[1]
    report_data = []

    for day in range(1, days_in_month + 1):
        selected_year = int(selected_year)
        selected_month = int(selected_month)
        date_str = f'{selected_year}-{selected_month:02d}-{day:02d}'
        daily_data = {'Date': date_str}

        for product_name in product_names_info:
            # Query the dispatch_db for the total quantity dispatched for this product on this date
            dispatched_data = dispatch_db.aggregate([
                {
                    "$match": {
                        "item": product_name,
                        "date": date_str  # Ensure the field name matches your DB schema
                    }
                },
                {
                    "$group": {
                        "_id": "$Product Name",
                        "totalDispatched": {"$sum": "$qty"}  # Replace 'Quantity' with your actual field name
                    }
                }
            ])

            # Extract the total dispatched quantity
            try:
                total_dispatched = next(dispatched_data)['totalDispatched']
            except StopIteration:
                total_dispatched = 0  # No data found for this product on this date

            daily_data[product_name] = total_dispatched

        report_data.append(daily_data)


    # List of months for dropdown
    months = list(calendar.month_name)[1:]

    return render_template('monthly_dispatch_report_liquid.html',
                           years=range(current_year - 5, current_year + 1),
                           months=months,
                           selected_year=int(selected_year),
                           selected_month=int(selected_month),
                           product_names=product_names_info,
                           report_data=report_data)

@app.route('/monthly_dispatch_report_granule', methods=['GET', 'POST'])
def monthly_dispatch_report_granule():
    current_year = datetime.now().year
    current_month = datetime.now().month

    selected_year = request.form.get('year', str(current_year))
    selected_month = request.form.get('month', str(current_month))

    # Fetch pack sizes and product names
    pack_sizes_info = net_inventory_granules_db.find({}, {"Pack Size": 1, "Product Name": 1})
    pack_size_to_product = {}
    for doc in pack_sizes_info:
        pack_size = doc.get("Pack Size")
        product_name = doc.get("Product Name")
        pack_size_to_product[pack_size] = product_name

    days_in_month = calendar.monthrange(int(selected_year), int(selected_month))[1]
    report_data = []

    for day in range(1, days_in_month + 1):
        date_str = f'{int(selected_year)}-{int(selected_month):02d}-{day:02d}'
        daily_data = {'Date': date_str}

        for pack_size, product_name in pack_size_to_product.items():
            # Query dispatch_db for total dispatched quantity
            total_dispatched = dispatch_db.aggregate([
                {"$match": {"item": product_name, "date": date_str}},
                {"$group": {"_id": None, "totalQty": {"$sum": "$qty"}}}
            ])

            try:
                dispatched_qty = next(total_dispatched)['totalQty']
            except StopIteration:
                dispatched_qty = 0

            daily_data[pack_size] = dispatched_qty

        report_data.append(daily_data)

    months = list(calendar.month_name)[1:]

    return render_template('monthly_dispatch_report_granule.html', years=range(current_year - 5, current_year + 1), months=months, selected_year=selected_year, selected_month=selected_month, pack_sizes=pack_size_to_product.keys(), report_data=report_data)


@app.route('/monthly_planning', methods=['GET', 'POST'])
def monthly_planning():
    # Fetch distinct 'Qty (pieces)' from Batch_sheet db
    qty_pieces = collection.distinct("Qty (pieces)")

    # Map 'Qty (pieces)' to 'Item' and get 'Qty' from production_sheet_db
    item_qty_mapping = {}
    for qty in qty_pieces:
        items = production_db.find({"Item": qty}, {"Item": 1, "Qty": 1})
        item_qty_mapping[qty] = {item['Item']: item['Qty'] for item in items}

    # Save to session
    session['item_qty_mapping'] = item_qty_mapping

    return render_template('monthly_planning.html', qty_pieces=qty_pieces, item_qty_mapping=item_qty_mapping)


@app.route('/submit_monthly_planning', methods=['POST'])
def submit_monthly_planning():
    form_data = request.form
    item_qty_mapping = session.get('item_qty_mapping', {})

    results = {}
    for key, value in form_data.items():
        if key.startswith("monthly_plan_"):
            qty_piece = key.split("_")[-1]
            try:
                monthly_plan = int(value) if value else 0
                monthly_expectation = int(form_data.get(f"monthly_expectation_{qty_piece}", 0))
            except ValueError:
                monthly_plan = 0
                monthly_expectation = 0

            total_item_qty = sum(int(qty) for qty in item_qty_mapping.get(qty_piece, {}).values())
            net_qty_required = monthly_expectation - (total_item_qty + monthly_plan)

            fg_rm_data = fg_rm_db.find({"Particulars": qty_piece})
            for data in fg_rm_data:
                for col_name, col_value in data.items():
                    if col_name not in ["Particulars", "Unit (ML)", "Unit (KG)", "Qty in 1 box", "_id"]:
                        if not isinstance(col_value, (int, float)):
                            continue  # Skip if col_value is not a number
                        if col_name not in results:
                            results[col_name] = 0
                        results[col_name] += (net_qty_required/fg_rm_data['']) * col_value

    return render_template('planning_results.html', results=results)




@app.route('/planning_results', methods=['GET', 'POST'])
def planning_results():
    if request.method == 'POST':
        form_data = request.form
        item_qty_mapping = session.get('item_qty_mapping', {})
        # Process the form data and perform calculations
        results = {}
        for key, value in form_data.items():
            if key.startswith("monthly_plan_"):
                qty_piece = key.split("_")[-1]
                monthly_plan = int(value)
                monthly_expectation = int(form_data.get(f"monthly_expectation_{qty_piece}", 0))
                item_qty = int(item_qty_mapping.get(qty_piece, 0))

                net_qty_required = monthly_expectation - (item_qty + monthly_plan)

                fg_rm_data = fg_rm_db.find({"Particulars": qty_piece})

                for data in fg_rm_data:
                    for col_name, col_value in data.items():
                        if col_name not in ["Particulars", "Unit (ML)", "Unit (KG)", "Qty in 1 box", "_id"]:
                            if col_name not in results:
                                results[col_name] = 0
                            results[col_name] += net_qty_required * col_value

        return render_template('planning_results.html', results=results)

    return redirect(url_for('monthly_planning'))

@app.route('/line_traveller')
def line_traveller():
    data = list(base_data_collection.find())
    return render_template('line_traveller.html', data=data)

@app.route('/edit_line_traveller/<batch_no>')
def edit_line_traveller(batch_no):
    return render_template('edit_form_line_traveller.html', batch_no=batch_no)

@app.route('/submit_line_traveller', methods=['POST'])
def submit_line_traveller():
    # Your existing logic to handle form data and generate Excel file

    # Example of creating an in-memory Excel file
    # Make sure to replace this with your actual Excel file creation logic
    excel_buffer = BytesIO()
    df = pd.DataFrame({'Example Column': ['Example Data']})  # Replace with real data
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)

    # Sending the Excel file as a download
    return send_file(
        excel_buffer,
        as_attachment=True,
        attachment_filename='updated_data.xlsx',  # Correct keyword argument here
        mimetype='application/vnd.ms-excel'
    )


if __name__ == '__main__':
    app.run(debug=True)
