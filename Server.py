import socket
import json
import threading
import mysql.connector
from datetime import datetime
import tkinter as tk
from tkinter import Listbox, Scrollbar, VERTICAL, LEFT, RIGHT, BOTH, Y

# Kết nối với MySQL
db = mysql.connector.connect(
    host="localhost",
    user='root',
    password='12345',  # Thay bằng mật khẩu MySQL của bạn
    database="gmail_clone"
)
cursor = db.cursor()

# Thông tin server
SERVER_ADDRESS = ('192.168.1.9', 12320)
BUFFER_SIZE = 4096

# Tạo socket UDP cho server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(SERVER_ADDRESS)

# Danh sách để lưu các hoạt động log
log_activities = []

admin_app = None  # Biến toàn cục cho GUI Admin

def log_activity(activity):
    """Ghi log hoạt động với timestamp và cập nhật GUI."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {activity}"
    print(log_message)  # In ra console để debug
    log_activities.append(log_message)

    # Cập nhật GUI admin nếu đã khởi tạo
    if admin_app:
        admin_app.update_log()

def handle_client_requests():
    """Xử lý yêu cầu từ client."""
    while True:
        try:
            # Nhận dữ liệu từ client
            data, address = server_socket.recvfrom(BUFFER_SIZE)
            message = json.loads(data.decode())

            if message['action'] == 'register_user':
                username = message['username']
                password = message['password']

                try:
                    cursor.execute(
                        "INSERT INTO users (username, password) VALUES (%s, %s)",
                        (username, password)
                    )
                    db.commit()
                    response = {'type': 'registration', 'message': f"User {username} registered successfully."}
                    log_activity(f"User {username} registered successfully.")
                except mysql.connector.IntegrityError:
                    response = {'type': 'error', 'message': f"User {username} already exists."}
                    log_activity(f"Failed to register {username}: User already exists.")

                server_socket.sendto(json.dumps(response).encode(), address)

            elif message['action'] == 'login_user':
                username = message['username']
                password = message['password']

                cursor.execute("SELECT password FROM users WHERE username = %s", (username,))
                result = cursor.fetchone()

                if result and result[0] == password:
                    response = {'type': 'login', 'message': f"User {username} logged in successfully."}
                    log_activity(f"User {username} logged in successfully.")
                else:
                    response = {'type': 'error', 'message': "Invalid username or password."}
                    log_activity(f"Failed login attempt for {username}.")

                server_socket.sendto(json.dumps(response).encode(), address)

            elif message['action'] == 'send_email':
                email = message['email']
                sender = email['from']
                recipient = email['to']
                subject = email['subject']
                content = email['content']

                cursor.execute(
                    "INSERT INTO emails (sender, recipient, subject, content) VALUES (%s, %s, %s, %s)",
                    (sender, recipient, subject, content)
                )
                db.commit()

                response = {'type': 'status', 'message': "Email sent successfully."}
                log_activity(f"Email from {sender} to {recipient} with subject '{subject}' sent.")
                server_socket.sendto(json.dumps(response).encode(), address)

            elif message['action'] == 'get_emails':
                username = message['user']

                cursor.execute(
                    "SELECT id, sender, subject, timestamp FROM emails WHERE recipient = %s", (username,)
                )
                emails = cursor.fetchall()
                email_list = [
                    f"{email[0]}. {email[1]} - {email[2]} ({email[3]})" for email in emails
                ]

                response = {'type': 'email_list', 'emails': email_list}
                log_activity(f"User {username} fetched email list.")
                server_socket.sendto(json.dumps(response).encode(), address)

            elif message['action'] == 'get_email_content':
                email_id = message['filename']

                cursor.execute(
                    "SELECT sender, recipient, subject, content, timestamp FROM emails WHERE id = %s",
                    (email_id,)
                )
                email = cursor.fetchone()

                if email:
                    email_data = {
                        'from': email[0], 'to': email[1],
                        'subject': email[2], 'content': email[3],
                        'timestamp': str(email[4])
                    }
                    response = {'type': 'email_content', 'email': email_data}
                    log_activity(f"User viewed email {email_id}.")
                else:
                    response = {'type': 'error', 'message': "Email not found."}
                    log_activity(f"Failed to retrieve email {email_id}.")

                server_socket.sendto(json.dumps(response).encode(), address)

        except json.JSONDecodeError:
            log_activity("Failed to decode JSON from client.")
        except Exception as e:
            log_activity(f"Unexpected error: {e}")

# Chạy server trong một luồng riêng
server_thread = threading.Thread(target=handle_client_requests, daemon=True)
server_thread.start()

# Tạo giao diện Admin để quản lý người dùng và log hoạt động
class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin - User Management and Activity Log")
        self.geometry("600x400")

        # Listbox người dùng
        self.user_listbox = Listbox(self, width=50, height=10)
        self.user_listbox.pack(pady=10)

        self.refresh_button = tk.Button(self, text="Refresh User List", command=self.refresh_user_list)
        self.refresh_button.pack(pady=5)

        # Log Listbox với thanh cuộn
        self.log_frame = tk.Frame(self)
        self.log_frame.pack(fill=BOTH, expand=True)

        self.log_scrollbar = Scrollbar(self.log_frame, orient=VERTICAL)
        self.log_listbox = Listbox(self.log_frame, yscrollcommand=self.log_scrollbar.set, width=100, height=15)
        self.log_scrollbar.config(command=self.log_listbox.yview)

        self.log_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        self.log_scrollbar.pack(side=RIGHT, fill=Y)

        self.refresh_user_list()
        self.update_log()

    def refresh_user_list(self):
        self.user_listbox.delete(0, tk.END)
        cursor.execute("SELECT username FROM users")
        users = cursor.fetchall()
        for user in users:
            self.user_listbox.insert(tk.END, user[0])

    def update_log(self):
        self.log_listbox.delete(0, tk.END)
        for log in log_activities:
            self.log_listbox.insert(tk.END, log)

# Tạo và chạy giao diện Admin
admin_app = AdminApp()
admin_app.mainloop()
