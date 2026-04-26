# -*- coding: utf-8 -*-
"""GMAIL VERIFIER - معدل للعمل على Railway"""

import smtplib
import dns.resolver
import socket
import concurrent.futures
import threading
import time
from datetime import datetime
import os
import random
from pathlib import Path

# ============================================
# الإعدادات - معدلة لـ Railway
# ============================================
MAX_WORKERS = 500  # أقل لـ Railway (2 CPU فقط)
BATCH_SIZE = 1000
SOCKET_TIMEOUT = 10
REQUEST_DELAY = 0.1

class GmailVerifier:
    """فحص حسابات Gmail مع تخزين النتائج"""

    def __init__(self, base_path="/app/data"):
        self.timeout = SOCKET_TIMEOUT
        self.delay = REQUEST_DELAY
        socket.setdefaulttimeout(self.timeout)

        # خوادم MX
        self.mx_servers = [
            'gmail-smtp-in.l.google.com',
            'alt1.gmail-smtp-in.l.google.com',
            'alt2.gmail-smtp-in.l.google.com',
            'alt3.gmail-smtp-in.l.google.com',
            'alt4.gmail-smtp-in.l.google.com'
        ]

        # المسار الرئيسي - متوافق مع Railway
        self.base_path = base_path
        self.disabled_folder = os.path.join(self.base_path, 'disabled')

        # إنشاء المجلدات
        self.create_folders()

        # إحصائيات
        self.stats = {
            'total': 0, 'live': 0, 'new_disabled': 0,
            'invalid': 0, 'error': 0, 'processed': 0,
            'files_processed': 0, 'total_files': 0
        }

        # حالة التشغيل
        self.is_running = False
        self.current_batch = 0
        self.total_batches = 0

        # أقفال
        self.stats_lock = threading.Lock()
        self.file_lock = threading.Lock()

        # مسارات الملفات
        self.live_file = os.path.join(self.base_path, 'live', 'live_accounts.txt')
        self.new_disabled_file = os.path.join(self.base_path, 'new_disabled', 'new_disabled_accounts.txt')
        self.invalid_file = os.path.join(self.base_path, 'invalid', 'invalid_accounts.txt')
        self.processed_file = os.path.join(self.base_path, 'processed', 'processed_accounts.txt')
        self.log_file = os.path.join(self.base_path, 'logs', f'session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

        # تحميل الحسابات المفحوصة
        self.processed_emails = self.load_processed()
        self.results = {'live': [], 'new_disabled': [], 'invalid': []}

    def create_folders(self):
        """إنشاء جميع المجلدات"""
        folders = [
            self.base_path,
            os.path.join(self.base_path, 'live'),
            self.disabled_folder,
            os.path.join(self.base_path, 'new_disabled'),
            os.path.join(self.base_path, 'invalid'),
            os.path.join(self.base_path, 'processed'),
            os.path.join(self.base_path, 'logs')
        ]

        for folder in folders:
            Path(folder).mkdir(parents=True, exist_ok=True)

    def get_all_disabled_files(self):
        """الحصول على جميع ملفات txt في مجلد disabled"""
        if not os.path.exists(self.disabled_folder):
            return []

        txt_files = []
        for file in os.listdir(self.disabled_folder):
            if file.endswith('.txt'):
                file_path = os.path.join(self.disabled_folder, file)
                txt_files.append(file_path)

        return sorted(txt_files)

    def load_processed(self):
        """تحميل الحسابات المفحوصة"""
        processed = set()
        if os.path.exists(self.processed_file):
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    processed = {line.strip().lower() for line in f if line.strip()}
            except Exception:
                pass
        return processed

    def save_processed(self, email):
        """حفظ حساب مفحوص"""
        try:
            with self.file_lock:
                with open(self.processed_file, 'a', encoding='utf-8') as f:
                    f.write(f"{email}\n")
        except:
            pass

    def save_result(self, email, status):
        """حفظ النتيجة"""
        try:
            if status == 'live':
                filepath = self.live_file
                self.results['live'].append(email)
            elif status == 'new_disabled':
                filepath = self.new_disabled_file
                self.results['new_disabled'].append(email)
            elif status == 'invalid':
                filepath = self.invalid_file
                self.results['invalid'].append(email)
            else:
                return

            with self.file_lock:
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(f"{email}\n")
        except:
            pass

    def verify_email(self, email, mx_server):
        """فحص حساب واحد"""
        server = None
        try:
            server = smtplib.SMTP(timeout=self.timeout)
            server.connect(mx_server, 25)
            server.helo('gmail.com')
            server.mail('verify@gmail.com')

            code, message = server.rcpt(email)
            server.quit()

            if code == 250:
                return 'live', "نشط"
            elif code == 550:
                msg = str(message).lower()
                if 'disabled' in msg or 'user disabled' in msg:
                    return 'new_disabled', "لا يزال معطل"
                else:
                    return 'invalid', "غير موجود"
            else:
                return 'error', f"كود {code}"

        except Exception as e:
            return 'error', str(e)[:30]
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass

    def load_emails_from_file(self, file_path):
        """تحميل الإيميلات من ملف محدد"""
        emails = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for line in lines:
                email = line.strip().lower()
                if email and '@' in email and email.endswith('@gmail.com'):
                    emails.append(email)

            return list(dict.fromkeys(emails))
        except Exception:
            return []

    def start_verification(self):
        """بدء عملية الفحص"""
        self.is_running = True
        self.results = {'live': [], 'new_disabled': [], 'invalid': []}

        # الحصول على جميع الملفات
        all_files = self.get_all_disabled_files()
        self.stats['total_files'] = len(all_files)

        if not all_files:
            return {'error': 'لا توجد ملفات في مجلد disabled'}

        # تجميع كل الإيميلات
        all_emails = []
        files_processed = 0

        for file_path in all_files:
            file_emails = self.load_emails_from_file(file_path)
            if file_emails:
                all_emails.extend(file_emails)
                files_processed += 1

            self.stats['files_processed'] = files_processed

        if not all_emails:
            return {'error': 'لا توجد إيميلات صالحة'}

        # إزالة التكرار
        all_emails = list(dict.fromkeys(all_emails))

        # تصفية المفحوص سابقاً
        new_emails = [e for e in all_emails if e not in self.processed_emails]

        if not new_emails:
            return {'message': 'جميع الحسابات مفحوصة مسبقاً', 'stats': self.stats}

        self.stats['total'] = len(new_emails)
        self.stats['start_time'] = time.time()

        # تقسيم إلى دفعات
        batches = [new_emails[i:i+BATCH_SIZE] for i in range(0, len(new_emails), BATCH_SIZE)]
        self.total_batches = len(batches)

        for batch_num, batch in enumerate(batches, 1):
            if not self.is_running:
                break

            self.current_batch = batch_num
            mx_server = random.choice(self.mx_servers)

            chunk_size = max(1, len(batch) // MAX_WORKERS)
            chunks = [batch[i:i+chunk_size] for i in range(0, len(batch), chunk_size)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for chunk in chunks:
                    future = executor.submit(self.verify_chunk, chunk, mx_server)
                    futures.append(future)
                concurrent.futures.wait(futures)

        self.is_running = False
        self.stats['end_time'] = time.time()
        return {'completed': True, 'stats': self.stats, 'results': self.results}

    def verify_chunk(self, email_chunk, mx_server):
        """فحص دفعة من الإيميلات"""
        for email in email_chunk:
            if not self.is_running:
                break

            if email in self.processed_emails:
                with self.stats_lock:
                    self.stats['processed'] += 1
                continue

            status, message = self.verify_email(email, mx_server)

            if status in ['live', 'new_disabled', 'invalid']:
                self.save_result(email, status)
                with self.stats_lock:
                    self.stats[status] += 1
                    self.stats['processed'] += 1
                    self.processed_emails.add(email)
                self.save_processed(email)
            else:
                with self.stats_lock:
                    self.stats['error'] += 1
                    self.stats['processed'] += 1

            time.sleep(self.delay)

    def stop_verification(self):
        """إيقاف الفحص"""
        self.is_running = False

    def get_status(self):
        """الحصول على حالة الفحص الحالية"""
        elapsed = 0
        speed = 0

        if self.stats.get('start_time') and self.stats['processed'] > 0:
            elapsed = time.time() - self.stats['start_time']
            speed = self.stats['processed'] / elapsed if elapsed > 0 else 0

        return {
            'is_running': self.is_running,
            'processed': self.stats['processed'],
            'total': self.stats['total'],
            'live': self.stats['live'],
            'new_disabled': self.stats['new_disabled'],
            'invalid': self.stats['invalid'],
            'error': self.stats['error'],
            'files_processed': self.stats['files_processed'],
            'total_files': self.stats['total_files'],
            'current_batch': self.current_batch,
            'total_batches': self.total_batches,
            'speed': int(speed),
            'elapsed': int(elapsed)
        }
