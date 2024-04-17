from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from flask_swagger_ui import get_swaggerui_blueprint
import sqlite3

app = Flask(__name__)

# Configure SQLite database
DATABASE = 'database.db'

def create_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # bills tablosunu oluştur
    c.execute('''CREATE TABLE IF NOT EXISTS bills (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 subscriber_no TEXT,
                 month TEXT,
                 total INTEGER,
                 details TEXT,
                 paid_status BOOLEAN,
                 FOREIGN KEY(subscriber_no) REFERENCES users(subscriber_no)
                 )''')

    # users tablosunu oluştur
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 subscriber_no TEXT UNIQUE,
                 password TEXT
                 )''')

    conn.commit()
    conn.close()

create_db()

def insert_data(subscriber_no, month, total, details, paid_status):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Verinin veritabanında olup olmadığını kontrol et
    c.execute("SELECT id FROM bills WHERE subscriber_no=? AND month=?", (subscriber_no, month))
    existing_record = c.fetchone()
    
    # Eğer veri yoksa, yeni veriyi ekle
    if existing_record is None:
        c.execute("INSERT INTO bills (subscriber_no, month, total, details, paid_status) VALUES (?, ?, ?, ?, ?)",
                  (subscriber_no, month, total, details, paid_status))
        conn.commit()
        print("Yeni veri eklendi.")
    else:
        print("Veri zaten veritabanında var.")
    
    conn.close()


# Kullanım örneği:
insert_data("ayşe", "2024-04", 100, "Some details", False)

def insert_user_data(subscriber_no, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Verinin veritabanında olup olmadığını kontrol et
    c.execute("SELECT id FROM users WHERE subscriber_no=?", (subscriber_no,))
    existing_record = c.fetchone()
    
    # Eğer veri yoksa, yeni veriyi ekle
    if existing_record is None:
        c.execute("INSERT INTO users (subscriber_no, password) VALUES (?, ?)",
                  (subscriber_no, password))
        conn.commit()
        print("Yeni kullanıcı eklendi.")
    else:
        print("Kullanıcı zaten veritabanında var.")
    
    conn.close()

# Kullanım örneği:
insert_user_data("admin", "123")


# Create Swagger UI blueprint
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
swagger_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Mobile Provider App APIs"
    }
)
app.register_blueprint(swagger_blueprint, url_prefix=SWAGGER_URL)

# Configure JWT
app.config['JWT_SECRET_KEY'] = 'super-secret'  # Change this!
jwt = JWTManager(app)

def authenticate_user(subscriber_no, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("SELECT subscriber_no, password FROM users WHERE subscriber_no=? AND password=?", (subscriber_no, password))
    user = c.fetchone()

    conn.close()
    return user

@app.route('/v1/login', methods=['POST'])
def login():
    subscriber_no = request.json.get('subscriber_no')
    password = request.json.get('password')

    if not subscriber_no or not password:
        return jsonify({"msg": "subscriber_no or password not provided"}), 400

    user = authenticate_user(subscriber_no, password)

    if user:
        access_token = create_access_token(identity=subscriber_no)
        return jsonify(access_token=access_token)
    else:
        return jsonify({"msg": "Invalid subscriber_no or password"}), 401
    
# Query Bill API
from flask_jwt_extended import jwt_required, get_jwt_identity

@app.route('/v1/query-bill', methods=['GET'])
@jwt_required()
def query_bill():
    subscriber_no = get_jwt_identity()  # Kullanıcı adını al

    # Eğer subscriber_no parametresi verilmişse, ve bu parametre token sahibi
    # kullanıcının adına eşit değilse, hata döndür
    requested_subscriber_no = request.args.get('subscriber_no')
    if requested_subscriber_no and requested_subscriber_no != subscriber_no:
        return jsonify({"error": "Invalid subscriber_no parameter"}), 400

    month = request.args.get('month')
    if not month:
        return jsonify({"error": "Month parameter is missing"}), 400

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    # Sorguyu token sahibi kullanıcının abone numarasına göre veya
    # subscriber_no parametresine göre yap
    if requested_subscriber_no:
        c.execute("SELECT total, paid_status FROM bills WHERE subscriber_no=? AND month=?", (requested_subscriber_no, month))
    else:
        c.execute("SELECT total, paid_status FROM bills WHERE subscriber_no=? AND month=?", (subscriber_no, month))
    
    bill_data = c.fetchone()
    conn.close()

    if bill_data:
        return jsonify({"bill_total": bill_data[0], "paid_status": bill_data[1]})
    else:
        return jsonify({"error": "Bill not found"}), 404


# Query Bill Detailed API with Pagination
@app.route('/v1/query-bill-detailed', methods=['GET'])
@jwt_required()
def query_bill_detailed():
    current_user = get_jwt_identity()  # Kullanıcı adını al
    requested_subscriber_no = request.args.get('subscriber_no')
    month = request.args.get('month')
    page = request.args.get('page', default=1, type=int)
    per_page = 10  # Sayfa başına istenen öğe sayısını ayarlayın

    # Eğer subscriber_no parametresi verilmişse, ve bu parametre token sahibi
    # kullanıcının adına eşit değilse, hata döndür
    if requested_subscriber_no and requested_subscriber_no != current_user:
        return jsonify({"error": "Invalid subscriber_no parameter"}), 400

    # Sorguyu token sahibi kullanıcının abone numarasına göre veya
    # subscriber_no parametresine göre yap
    if requested_subscriber_no:
        subscriber_no = requested_subscriber_no
    else:
        subscriber_no = current_user

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT total, details FROM bills WHERE subscriber_no=? AND month=?", (subscriber_no, month))
    all_data = c.fetchall()
    conn.close()

    if not all_data:
        return jsonify({"error": "No detailed bill found"}), 404
    
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_data = all_data[start_index:end_index]

    return jsonify({"detailed_bill": paginated_data})

@app.route('/v1/banking-app/query-bill', methods=['GET'])
@jwt_required()
def banking_query_bill():
    current_user = get_jwt_identity()  # Kullanıcı adını al
    requested_subscriber_no = request.args.get('subscriber_no')
    
    # Eğer subscriber_no parametresi verilmişse, ve bu parametre token sahibi
    # kullanıcının adına eşit değilse, hata döndür
    if requested_subscriber_no and requested_subscriber_no != current_user:
        return jsonify({"error": "Invalid subscriber_no parameter"}), 400

    # Sorguyu token sahibi kullanıcının abone numarasına göre veya
    # subscriber_no parametresine göre yap
    if requested_subscriber_no:
        subscriber_no = requested_subscriber_no
    else:
        subscriber_no = current_user

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT month FROM bills WHERE subscriber_no=? AND paid_status=?", (subscriber_no, False))
    unpaid_bills = c.fetchall()
    conn.close()

    if unpaid_bills:
        return jsonify({"unpaid_bills": unpaid_bills})
    else:
        return jsonify({"message": "No unpaid bills found for the subscriber"}), 404



# Pay Bill API
@app.route('/v1/website/pay-bill', methods=['POST'])
def pay_bill():
    subscriber_no = request.json.get('subscriber_no')
    month = request.json.get('month')

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Abonenin numarası ve ayıyla eşleşen faturanın durumunu sorgula
    c.execute("SELECT paid_status FROM bills WHERE subscriber_no=? AND month=?", (subscriber_no, month))
    bill_status = c.fetchone()

    if not bill_status:
        conn.close()
        return jsonify({"error": "Bill not found"}), 404

    if bill_status[0]:  # Fatura ödenmişse
        conn.close()
        return jsonify({"payment_status": "Successful", "message": "Payment successful."})
    else:  # Fatura ödenmemişse
        conn.close()
        return jsonify({"payment_status": "Error", "message": "Invoice not paid."}), 400



# Admin - Add Bill API
@app.route('/v1/website/admin/add-bill', methods=['POST'])
@jwt_required()
def add_bill():
    current_user = get_jwt_identity()

    # Admin kullanıcısının token'ını al
    admin_username = "admin"  # varsayılan olarak "admin" kullanıcı adını kabul edelim

    # Sadece admin kullanıcısı için işlemi sürdür
    if current_user != admin_username:
        return jsonify({"error": "Unauthorized"}), 401

    # Diğer işlemler devam eder
    subscriber_no = request.json.get('subscriber_no')
    month = request.json.get('month')
    total = request.json.get('total')
    details = request.json.get('details')
    paid_status = request.json.get('paid_status')

    # Faturanın veritabanında zaten var olup olmadığını kontrol et
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT id FROM bills WHERE subscriber_no=? AND month=?", (subscriber_no, month))
    existing_record = c.fetchone()
    if existing_record:
        return jsonify({"error": "Bill already exists for the subscriber and month"}), 400

    # Faturayı ekle
    c.execute("INSERT INTO bills (subscriber_no, month, total, details, paid_status) VALUES (?, ?, ?, ?, ?)",
              (subscriber_no, month, total, details, paid_status))
    conn.commit()
    conn.close()

    return jsonify({"transaction_status": "Bill added successfully"})

if __name__ == '__main__':
    create_db()
    app.run(debug=True)
