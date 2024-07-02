import socket       # โมดูลสำหรับการจัดการ socket และเชื่อมต่อเครือข่าย
import threading    # โมดูลสำหรับการจัดการ thread เพื่อการทำงานพร้อมกันหลายงาน
import json         # โมดูลสำหรับการจัดการ JSON (การแปลงข้อมูลเป็นและจาก JSON)
import sys          # โมดูลสำหรับการจัดการกับระบบ (system)
import os           # โมดูลสำหรับการจัดการไฟล์และเปิดใช้งานระบบปฏิบัติการ
import secrets      # โมดูลสำหรับการจัดการค่าสุ่มที่มีความปลอดภัย (เช่น การสร้างคีย์สำหรับการเข้ารหัส)

class Node:
    def __init__(self, host, port):
        self.host = host  # กำหนด host ของโหนด
        self.port = port  # กำหนด port ของโหนด
        self.peers = []  # เก็บรายการ socket ของ peer ที่เชื่อมต่อ
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # สร้าง socket สำหรับโหนดนี้
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ตั้งค่า socket ให้สามารถใช้งานได้ซ้ำ
        self.transactions = []  # เก็บรายการ transactions ที่ได้รับหรือส่ง
        self.transaction_file = f"transactions_{port}.json"  # ชื่อไฟล์สำหรับบันทึก transactions ของโหนดนี้
        self.wallet_address = self.generate_wallet_address()  # สร้าง wallet address สำหรับโหนดนี้โดยใช้เมธอด generate_wallet_address()

    def generate_wallet_address(self):
    # สร้าง wallet address แบบง่ายๆ (ในระบบจริงจะซับซ้อนกว่านี้มาก)
        return '0x' + secrets.token_hex(20)
    
    def start(self):
        # กำหนด socket ให้ bind กับ host และ port ที่กำหนด
        self.socket.bind((self.host, self.port))
        
        # ให้ socket รอการเชื่อมต่อจาก client สูงสุด 1 คน
        self.socket.listen(1)
        
        # พิมพ์ข้อความยืนยันว่าโหนดได้เริ่มต้นการทำงานแล้ว
        print(f"Node listening on {self.host}:{self.port}")
        
        # พิมพ์ wallet address ของโหนด
        print(f"Your wallet address is: {self.wallet_address}")

        # โหลด transactions จากไฟล์ (ถ้ามี)
        self.load_transactions()

        # เริ่ม thread สำหรับรับการเชื่อมต่อใหม่
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.start()

    def accept_connections(self):
        while True:
            # รอรับการเชื่อมต่อใหม่
            client_socket, address = self.socket.accept()
            print(f"New connection from {address}")

            # เริ่ม thread ใหม่สำหรับจัดการการเชื่อมต่อนี้
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()
    
    def handle_client(self, client_socket):
        # เริ่มลูปที่ทำงานตลอดจนกว่าจะมีการ break ออกจากลูป
        while True:
            try:
                # รับข้อมูลจาก client ขนาดสูงสุด 1024 ไบต์
                data = client_socket.recv(1024)
                
                # หากไม่ได้รับข้อมูล (data ว่างเปล่า) ให้ break ออกจากลูป
                if not data:
                    break

                # แปลงข้อมูลที่ได้รับจากไบต์เป็นสตริง และแปลงสตริง JSON เป็นวัตถุ Python
                message = json.loads(data.decode('utf-8'))
                
                # ประมวลผลข้อความที่ได้รับจาก client
                self.process_message(message, client_socket)

            except Exception as e:
                # หากเกิดข้อผิดพลาด ให้พิมพ์ข้อความแสดงข้อผิดพลาดและ break ออกจากลูป
                print(f"Error handling client: {e}")
                break

        # ปิดการเชื่อมต่อกับ client
        client_socket.close()
    
    def connect_to_peer(self, peer_host, peer_port):
        try:
            # สร้างการเชื่อมต่อไปยัง peer
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # สร้าง socket สำหรับการเชื่อมต่อแบบ TCP/IP
            peer_socket.connect((peer_host, peer_port))  # เชื่อมต่อไปยัง peer ที่ระบุด้วย host และ port
            self.peers.append(peer_socket)  # เพิ่ม socket ของ peer นี้เข้าไปในรายการ peers
            print(f"Connected to peer {peer_host}:{peer_port}")  # แสดงข้อความยืนยันการเชื่อมต่อ

            # ขอข้อมูล transactions ทั้งหมดจาก peer ที่เชื่อมต่อ
            self.request_sync(peer_socket)  # เรียกเมธอด request_sync เพื่อขอข้อมูล transactions จาก peer

            # เริ่ม thread สำหรับรับข้อมูลจาก peer นี้
            peer_thread = threading.Thread(target=self.handle_client, args=(peer_socket,))  # สร้าง thread ใหม่เพื่อจัดการการรับข้อมูลจาก peer
            peer_thread.start()  # เริ่ม thread ใหม่

        except Exception as e:
            print(f"Error connecting to peer: {e}")  # หากเกิดข้อผิดพลาด ให้แสดงข้อความข้อผิดพลาด

    def broadcast(self, message):
        # ส่งข้อมูลไปยังทุก peer ที่เชื่อมต่ออยู่
        for peer_socket in self.peers:
            try:
                peer_socket.send(json.dumps(message).encode('utf-8'))  # แปลง message เป็น JSON และส่งไปยัง peer นั้นๆ
            except Exception as e:
                print(f"Error broadcasting to peer: {e}")  # หากเกิดข้อผิดพลาดในการส่งข้อมูล ให้แสดงข้อความข้อผิดพลาด
                self.peers.remove(peer_socket)  # ลบ peer ที่เกิดข้อผิดพลาดออกจากรายการ peers
    def process_message(self, message, client_socket):
        # ประมวลผลข้อความที่ได้รับ
        if message['type'] == 'transaction':
            print(f"Received transaction: {message['data']}")
            self.add_transaction(message['data'])  # เพิ่ม transaction ลงในรายการ transactions
        elif message['type'] == 'sync_request':
            self.send_all_transactions(client_socket)  # ส่งข้อมูล transactions ทั้งหมดไปยัง client_socket
        elif message['type'] == 'sync_response':
            self.receive_sync_data(message['data'])  # รับข้อมูลการ sync ที่ส่งกลับมา
        else:
            print(f"Received message: {message}")  # ปริ้นข้อความที่ได้รับหากไม่ตรงกับเงื่อนไขข้างต้น
    def add_transaction(self, transaction):
        # เพิ่ม transaction ใหม่และบันทึกลงไฟล์
        if transaction not in self.transactions:  # ตรวจสอบว่า transaction ยังไม่มีอยู่ในรายการ transactions
            self.transactions.append(transaction)  # เพิ่ม transaction เข้าไปในรายการ transactions
            self.save_transactions()  # เรียกใช้เมธอด save_transactions เพื่อบันทึก transactions ลงในไฟล์
            print(f"Transaction added and saved: {transaction}")  # พิมพ์ข้อความแสดงว่าเพิ่มและบันทึก transaction เรียบร้อยแล้ว

    def create_transaction(self, recipient, amount):
        # สร้าง transaction ใหม่
        transaction = {
            'sender': self.wallet_address,
            'recipient': recipient,
            'amount': amount
        }
        
        # เรียกใช้เมธอด add_transaction เพื่อเพิ่ม transaction ลงในรายการ transactions ของโหนด
        self.add_transaction(transaction)
        
        # กระจายข้อมูล transaction ไปยังทุก peer ที่เชื่อมต่ออยู่
        self.broadcast({'type': 'transaction', 'data': transaction})

    def save_transactions(self):
    # บันทึก transactions ลงไฟล์
        with open(self.transaction_file, 'w') as f:
            json.dump(self.transactions, f)

    def load_transactions(self):
        # โหลด transactions จากไฟล์ (ถ้ามี)
        if os.path.exists(self.transaction_file):  # ตรวจสอบว่าไฟล์ transaction_file มีอยู่หรือไม่
            with open(self.transaction_file, 'r') as f:  # เปิดไฟล์สำหรับอ่าน ('r')
                self.transactions = json.load(f)  # โหลดข้อมูล transactions จากไฟล์และเก็บไว้ในตัวแปร self.transactions
            print(f"Loaded {len(self.transactions)} transactions from file.")  # พิมพ์จำนวน transactions ที่โหลดมาจากไฟล์

    def request_sync(self, peer_socket):
        # ส่งคำขอซิงโครไนซ์ไปยัง peer
        sync_request = json.dumps({"type": "sync_request"}).encode('utf-8')  # สร้างข้อมูล sync_request และ encode เป็น UTF-8
        peer_socket.send(sync_request)  # ส่งข้อมูล sync_request ไปยัง peer_socket

    def send_all_transactions(self, client_socket):
        # ส่ง transactions ทั้งหมดไปยังโหนดที่ขอซิงโครไนซ์
        sync_data = json.dumps({
            "type": "sync_response",
            "data": self.transactions
        }).encode('utf-8')  # สร้างข้อมูล sync_response ที่ประกอบด้วยประเภทของข้อมูลและ transactions ทั้งหมด และ encode เป็น UTF-8
        client_socket.send(sync_data)  # ส่งข้อมูล sync_response ไปยัง client_socket

    def receive_sync_data(self, sync_transactions):
        # รับและประมวลผลข้อมูล transactions ที่ได้รับจากการซิงโครไนซ์
        for tx in sync_transactions:  # วนลูปในรายการ sync_transactions
            self.add_transaction(tx)  # เรียกใช้เมธอด add_transaction เพื่อเพิ่ม transaction ลงในรายการ transactions ของโหนดปัจจุบัน
        print(f"Synchronized {len(sync_transactions)} transactions.")  # พิมพ์จำนวน transactions ที่ซิงโครไนซ์มาสำเร็จ

if __name__ == "__main__":
        if len(sys.argv) != 2:  # ตรวจสอบว่าจำนวน argument ที่ส่งเข้ามาถูกต้องหรือไม่
            print("Usage: python script.py <port>")  # แสดงวิธีการใช้งานที่ถูกต้อง
            sys.exit(1)  # ออกจากโปรแกรมถ้าจำนวน argument ไม่ถูกต้อง
        
        port = int(sys.argv[1])  # ดึง port จาก argument
        node = Node("0.0.0.0", port)  # สร้าง instance ของ Node ใช้ "0.0.0.0" เพื่อรับการเชื่อมต่อจากภายนอก
        node.start()  # เริ่มต้นการทำงานของ node
        
        while True:
            # แสดงเมนูให้ผู้ใช้เลือก
            print("\n1. Connect to a peer")
            print("2. Create a transaction")
            print("3. View all transactions")
            print("4. View my wallet address")
            print("5. Exit")
            choice = input("Enter your choice: ")

            if choice == '1':
                peer_host = input("Enter peer host to connect: ")  # รับ host ของ peer ที่จะเชื่อมต่อ
                peer_port = int(input("Enter peer port to connect: "))  # รับ port ของ peer ที่จะเชื่อมต่อ
                node.connect_to_peer(peer_host, peer_port)  # เชื่อมต่อกับ peer
            elif choice == '2':
                recipient = input("Enter recipient wallet address: ")  # รับที่อยู่ของผู้รับ
                amount = float(input("Enter amount: "))  # รับจำนวนเงินที่จะส่ง
                node.create_transaction(recipient, amount)  # สร้าง transaction ใหม่
            elif choice == '3':
                print("All transactions:")  # แสดงรายการ transactions ทั้งหมด
                for tx in node.transactions:
                    print(tx)  # แสดง transaction แต่ละรายการ
            elif choice == '4':
                print(f"Your wallet address is: {node.wallet_address}")  # แสดง wallet address ของโหนดนี้
            elif choice == '5':
                break
            else:
                print("Invalid choice. Please try again.")

print("Exiting...")