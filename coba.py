import os
import hashlib
import pandas as pd
from datetime import datetime
from functools import wraps
import locale # Tambahkan ini untuk format angka

# Impor library Flask
from flask import (
    Flask, 
    render_template_string,
    request, 
    redirect, 
    url_for, 
    session, 
    flash
    # Menghapus 'jsonify' karena tidak terpakai
)

# --- Path Absolut (Sudah Benar) ---
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Inisialisasi Aplikasi Flask
app = Flask(__name__)

# --- Kunci Rahasia (Sudah Benar) ---
app.secret_key = 'kunci-rahasia-lokal-saya-bebas-diisi-apa-saja'

# --- Fungsi Format Rupiah (Sudah Benar) ---
def format_rupiah(value):
    """Format angka menjadi string Rupiah 'Rp 1.000.000'."""
    try:
        try:
            locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_ALL, 'Indonesian_Indonesia.1252')
            
        value = float(value)
        formatted_value = locale.format_string("%d", value, grouping=True)
        return f"Rp {formatted_value}"
    except (ValueError, TypeError, locale.Error):
        try:
            return f"Rp {int(value):,}".replace(",", ".")
        except:
             return "Rp 0"

# Daftarkan fungsi sebagai filter Jinja2
app.jinja_env.filters['rupiah'] = format_rupiah
# --- Akhir Perbaikan ---


# ---------------- Data Kategori (Ikan Koi) ----------------
kategori_pengeluaran = {
    "Beban Utilitas": ["Beban Listrik", "Beban Air", "Beban Telepon/Internet"],
    "Beban Gaji & Upah": ["Beban Gaji Karyawan", "Upah Harian Lepas"],
    "Beban Pemeliharaan": ["Beban Reparasi Kendaraan", "Beban Reparasi Bangunan"],
    "Beban Perlengkapan": ["Beban Pakan Ikan", "Beban Obat/Vitamin", "Beban Filtrasi", "Beban Garam Ikan"],
    "Beban Penyusutan": ["Beban Penyusutan Bangunan", "Beban Penyusutan Kendaraan"],
    "Lainnya": ["Lain-lain"]
}
kategori_pemasukan = {
    "Sumber Pemasukan": ["Penjualan Ikan Koi", "Lain-lain"]
}

# --- [PERBAIKAN BUG 'columns_map'] Pindahkan definisi ini ke global scope ---
columns_map = {
    "pemasukan.csv": ["Tanggal", "Sumber", "Jumlah", "Metode", "Keterangan", "Username", "Kontak"],
    "pengeluaran.csv": ["Tanggal", "Kategori", "Sub Kategori", "Jumlah", "Keterangan", "Metode", "Username", "Kontak"],
    "jurnal.csv": ["Tanggal", "Akun", "Debit", "Kredit", "Keterangan", "Kontak"]
}
# --- Akhir Perbaikan ---

# ---------------- Helper Functions ----------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_file(base_filename, username):
    name, ext = os.path.splitext(base_filename)
    filename = f"{name}_{username}{ext}"
    return os.path.join(APP_DIR, filename)

def load_data(base_filename, username):
    filename = get_user_file(base_filename, username)
    
    # [DIHAPUS] Definisi columns_map dipindah ke global scope
    
    if os.path.exists(filename):
        try:
            return pd.read_csv(filename)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=columns_map.get(base_filename, []))
    else:
        return pd.DataFrame(columns=columns_map.get(base_filename, []))

def save_data(df, base_filename, username):
    filename = get_user_file(base_filename, username)
    df.to_csv(filename, index=False)

def append_data(data, base_filename, username):
    df = load_data(base_filename, username)
    
    new_data_df = pd.DataFrame([data])
    
    if df.empty:
        df_columns = columns_map.get(base_filename) # <-- Ini sekarang akan berhasil
        if df_columns is None:
            df_columns = list(data.keys())
        df = pd.DataFrame(columns=df_columns)

    for col in new_data_df.columns:
        if col not in df.columns:
            df[col] = pd.NA

    for col in df.columns:
        if col not in new_data_df.columns:
            new_data_df[col] = pd.NA

    new_data_df = new_data_df[df.columns]
    
    df = pd.concat([df, new_data_df], ignore_index=True)
    save_data(df, base_filename, username)


def buat_jurnal(tanggal, akun_debit, akun_kredit, jumlah, keterangan, kontak=""):
    kontak_debit = kontak if akun_debit in ["Piutang Dagang", "Utang Dagang"] else ""
    kontak_kredit = kontak if akun_kredit in ["Piutang Dagang", "Utang Dagang"] else ""
    
    return [
        {"Tanggal": tanggal, "Akun": akun_debit, "Debit": jumlah, "Kredit": 0, "Keterangan": keterangan, "Kontak": kontak_debit},
        {"Tanggal": tanggal, "Akun": akun_kredit, "Debit": 0, "Kredit": jumlah, "Keterangan": keterangan, "Kontak": kontak_kredit},
    ]

def load_user_accounts():
    akun_file = os.path.join(APP_DIR, "akun.csv")
    if os.path.exists(akun_file):
        try:
            return pd.read_csv(akun_file)
        except pd.errors.EmptyDataError:
             return pd.DataFrame(columns=["Username", "Password"])
    else:
        return pd.DataFrame(columns=["Username", "Password"])

def save_user_accounts(df):
    akun_file = os.path.join(APP_DIR, "akun.csv")
    df.to_csv(akun_file, index=False)

def register_user(username, password):
    akun_df = load_user_accounts()
    if not akun_df.empty and (akun_df['Username'] == username).any():
        return False
    akun_df = pd.concat([akun_df, pd.DataFrame([{"Username": username, "Password": hash_password(password)}])], ignore_index=True)
    save_user_accounts(akun_df)
    return True

def validate_login(username, password):
    akun_df = load_user_accounts()
    if akun_df.empty:
        return False
    hashed_pw = hash_password(password)
    user_data = akun_df[(akun_df['Username'] == username) & (akun_df['Password'] == hashed_pw)]
    return not user_data.empty

def hapus_transaksi(transaksi_type, index_to_delete, username):
    base_filename = f"{transaksi_type}.csv"
    df = load_data(base_filename, username)
    
    try:
        index_to_delete = int(index_to_delete)
        
        if index_to_delete in df.index:
            transaksi = df.loc[index_to_delete]
            df = df.drop(index_to_delete).reset_index(drop=True)
            save_data(df, base_filename, username)
            
            waktu_hapus = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            keterangan_batal = f"Pembatalan: {transaksi.get('Keterangan', '')}"
            jumlah_transaksi = transaksi['Jumlah']
            metode_transaksi = transaksi['Metode']
            kontak = transaksi.get('Kontak', '')
            
            if transaksi_type == "pemasukan":
                if metode_transaksi == "Pelunasan Piutang":
                    jurnal_pembalikan = buat_jurnal(waktu_hapus, "Piutang Dagang", "Kas", jumlah_transaksi, keterangan_batal, kontak)
                else:
                    akun_debit = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang"}.get(metode_transaksi, "Kas")
                    jurnal_pembalikan = buat_jurnal(waktu_hapus, "Pendapatan", akun_debit, jumlah_transaksi, keterangan_batal, kontak)
            
            elif transaksi_type == "pengeluaran":
                if metode_transaksi == "Pelunasan Utang":
                    jurnal_pembalikan = buat_jurnal(waktu_hapus, "Kas", "Utang Dagang", jumlah_transaksi, keterangan_batal, kontak)
                else:
                    akun_kredit = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang"}.get(metode_transaksi, "Kas")
                    sub_kategori = transaksi.get('Sub Kategori', 'Beban Lain')
                    jurnal_pembalikan = buat_jurnal(waktu_hapus, akun_kredit, sub_kategori, jumlah_transaksi, keterangan_batal, kontak)
            else:
                return False

            for j in jurnal_pembalikan:
                append_data(j, "jurnal.csv", username)
            return True
        else:
            return False
    except (ValueError, TypeError):
        return False
    

# ---------------- Decorator (Sama) ----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash("Harap login terlebih dahulu.", "danger")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- KUMPULAN TEMPLATE HTML ----------------

# HTML_LAYOUT (Sudah ada script formatRupiah)
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Aplikasi Keuangan</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <nav class="bg-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex">
                    <!-- [UBAH] Tema Merah -->
                    <a href="{{ url_for('index_page') }}" class="flex-shrink-0 flex items-center text-xl font-bold text-red-700">
                         KoiAkun (Lokal)
                    </a>
                </div>
                <div class="flex items-center">
                    {% if session.logged_in %}
                        <span class="text-gray-700 mr-4">Halo, {{ session.username }}!</span>
                        <a href="{{ url_for('index_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Beranda</a>
                        <a href="{{ url_for('pemasukan_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Pemasukan</a>
                        <!-- [UBAH] "Beban" -> "Pengeluaran" -->
                        <a href="{{ url_for('pengeluaran_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Pengeluaran</a>
                        <a href="{{ url_for('kelola_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Kelola Data</a>
                        <a href="{{ url_for('laporan_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Laporan</a>
                        <a href="{{ url_for('logout_page') }}" class="ml-4 px-3 py-2 rounded-md text-sm font-medium text-red-600 bg-red-100 hover:bg-red-200">Logout</a>
                    {% else %}
                        <!-- [UBAH] Tema Merah -->
                        <a href="{{ url_for('login_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-red-600 bg-red-100 hover:bg-red-200">Login</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    
    <main>
        <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
            <!-- Pesan Flash (Notifikasi) -->
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="{% if category == 'success' %}bg-green-100 border-green-400 text-green-700{% else %}bg-red-100 border-red-400 text-red-700{% endif %} border px-4 py-3 rounded-md relative mb-4" role="alert">
                    <span class="block sm:inline">{{ message }}</span>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
        
            <!-- Konten Halaman -->
            {% block content %}{% endblock %}
        </div>
    </main>
    
    <!-- Script format Rupiah & Toggle -->
    <script>
        function formatRupiah(element) {
            let value = element.value.replace(/[^,\d]/g, '').toString();
            let split = value.split(',');
            let sisa = split[0].length % 3;
            let rupiah = split[0].substr(0, sisa);
            let ribuan = split[0].substr(sisa).match(/\d{3}/gi);

            if (ribuan) {
                let separator = sisa ? '.' : '';
                rupiah += separator + ribuan.join('.');
            }

            rupiah = split[1] != undefined ? rupiah + ',' + split[1] : rupiah;
            element.value = rupiah;
        }

        function toggleKontakInput(metodeName, inputContainerId) {
            const container = document.getElementById(inputContainerId);
            if (!container) return; 
            
            const radios = document.getElementsByName(metodeName);
            let selectedValue = '';
            for (const radio of radios) {
                if (radio.checked) {
                    selectedValue = radio.value;
                    break;
                }
            }

            if (selectedValue === 'Piutang' || selectedValue === 'Utang' || selectedValue === 'Pelunasan Piutang' || selectedValue === 'Pelunasan Utang') {
                container.style.display = 'block';
            } else {
                container.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""


HTML_LOGIN = """
<div class="flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-xl shadow-lg">
        <div>
            <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
                Login atau Daftar Akun (Lokal)
            </h2>
        </div>
        <form class="mt-8 space-y-6" action="{{ url_for('login_page') }}" method="POST">
            <div class="rounded-md shadow-sm -space-y-px">
                <div>
                    <label for="username" class="sr-only">Nama Pengguna</label>
                    <!-- [UBAH] Tema Merah -->
                    <input id="username" name="username" type="text" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" placeholder="Nama Pengguna">
                </div>
                <div>
                    <label for="password" class="sr-only">Kata Sandi</label>
                    <!-- [UBAH] Tema Merah -->
                    <input id="password" name="password" type="password" required class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" placeholder="Kata Sandi">
                </div>
            </div>

            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <!-- [UBAH] Tema Merah -->
                    <input id="mode-login" name="mode" type="radio" value="Login" checked class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="mode-login" class="ml-2 block text-sm text-gray-900"> Login </label>
                </div>
                <div class="flex items-center">
                    <!-- [UBAH] Tema Merah -->
                    <input id="mode-daftar" name="mode" type="radio" value="Daftar" class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="mode-daftar" class="ml-2 block text-sm text-gray-900"> Daftar </label>
                </div>
            </div>

            <div>
                <!-- [UBAH] Tema Merah -->
                <button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                    Kirim
                </button>
            </div>
        </form>
    </div>
</div>
"""

HTML_INDEX = """
<div class="bg-white p-8 rounded-xl shadow-lg">
    <h1 class="text-3xl font-bold text-gray-900 mb-4">Selamat datang, {{ session.username }}!</h1>
    <p class="text-gray-700 text-lg">Ini adalah aplikasi akuntansi KoiAkun versi web.</p>
    <ul class="list-disc list-inside mt-4 text-gray-600">
        <li>Gunakan menu <b class="text-red-600">Pemasukan</b> untuk mencatat pendapatan.</li>
        <!-- [UBAH] "Beban" -> "Pengeluaran" & Tema Merah -->
        <li>Gunakan menu <b class="text-red-600">Pengeluaran</b> untuk mencatat biaya operasional.</li>
        <li>Gunakan menu <b class="text-red-600">Kelola Data</b> untuk melihat dan menghapus transaksi.</li>
        <li>Gunakan menu <b class="text-red-600">Laporan</b> untuk melihat analisis keuangan Anda, termasuk Buku Besar Pembantu.</li>
    </ul>
</div>
"""

HTML_PEMASUKAN = """
<div class="bg-white p-8 rounded-xl shadow-lg max-w-2xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Tambah Pemasukan</h2>
    <form action="{{ url_for('pemasukan_page') }}" method="POST" class="space-y-4">
        <div>
            <label for="tanggal" class="block text-sm font-medium text-gray-700">Tanggal</label>
            <!-- [UBAH] Tema Merah -->
            <input type="date" id="tanggal" name="tanggal" value="{{ today }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <div>
            <label for="sumber" class="block text-sm font-medium text-gray-700">Sumber Pemasukan</label>
            <!-- [UBAH] Tema Merah -->
            <select id="sumber" name="sumber" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                {% for sumber in kategori_pemasukan['Sumber Pemasukan'] %}
                <option value="{{ sumber }}">{{ sumber }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label for="jumlah" class="block text-sm font-medium text-gray-700">Jumlah (Rp)</label>
            <!-- [UBAH] Tema Merah -->
            <input type="text" id="jumlah" name="jumlah" min="0" required inputmode="numeric"
                   onkeyup="formatRupiah(this)"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Contoh: 1.000.000">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Metode Penerimaan</label>
            <div class="mt-2 space-y-2" onchange="toggleKontakInput('metode_pemasukan', 'kontak-pemasukan-container')">
                {% for metode in ['Tunai', 'Transfer', 'Piutang', 'Pelunasan Piutang'] %}
                <div class="flex items-center">
                    <!-- [UBAH] Tema Merah -->
                    <input id="metode-{{ loop.index }}" name="metode_pemasukan" type="radio" value="{{ metode }}" {% if loop.first %}checked{% endif %}
                           class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="metode-{{ loop.index }}" class="ml-3 block text-sm font-medium text-gray-700">{{ metode }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div id="kontak-pemasukan-container" style="display:none;">
            <label for="kontak_pemasukan" class="block text-sm font-medium text-gray-700">Nama Pelanggan</label>
            <!-- [UBAH] Tema Merah -->
            <input type="text" id="kontak_pemasukan" name="kontak"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Masukkan nama pelanggan">
        </div>
        
        <div>
            <label for="deskripsi" class="block text-sm font-medium text-gray-700">Keterangan (opsional)</label>
            <!-- [UBAH] Tema Merah -->
            <textarea id="deskripsi" name="deskripsi" rows="3"
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Catatan tambahan..."></textarea>
        </div>
        <div>
            <!-- [UBAH] Tema Merah -->
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                ✅ Simpan Pemasukan
            </button>
        </div>
    </form>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            toggleKontakInput('metode_pemasukan', 'kontak-pemasukan-container');
        });
    </script>
</div>
"""

HTML_PENGELUARAN = """
<div class="bg-white p-8 rounded-xl shadow-lg max-w-2xl mx-auto">
    <!-- [UBAH] "Beban" -> "Pengeluaran" -->
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Tambah Pengeluaran</h2>
    <form action="{{ url_for('pengeluaran_page') }}" method="POST" class="space-y-4">
        <div>
            <label for="tanggal" class="block text-sm font-medium text-gray-700">Tanggal</label>
            <!-- [UBAH] Tema Merah -->
            <input type="date" id="tanggal" name="tanggal" value="{{ today }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <div>
            <!-- [UBAH] "Beban" -> "Pengeluaran" -->
            <label for="kategori" class="block text-sm font-medium text-gray-700">Kategori Pengeluaran</label>
            <!-- [UBAH] Tema Merah -->
            <select id="kategori" name="kategori" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                {% for kategori in kategori_pengeluaran.keys() %}
                <option value="{{ kategori }}">{{ kategori }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label for="sub_kategori" class="block text-sm font-medium text-gray-700">Sub Kategori (Akun)</label>
            <!-- [UBAH] Tema Merah -->
            <select id="sub_kategori" name="sub_kategori" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                <!-- Opsi akan diisi oleh JavaScript -->
            </select>
        </div>
        <div>
            <label for="jumlah" class="block text-sm font-medium text-gray-700">Jumlah (Rp)</label>
            <!-- [UBAH] Tema Merah -->
            <input type="text" id="jumlah" name="jumlah" min="0" required inputmode="numeric"
                   onkeyup="formatRupiah(this)"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Contoh: 150.000">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Metode Pembayaran</label>
            <div class="mt-2 space-y-2" onchange="toggleKontakInput('metode_pengeluaran', 'kontak-pengeluaran-container')">
                {% for metode in ['Tunai', 'Transfer', 'Utang', 'Pelunasan Utang'] %}
                <div class="flex items-center">
                    <!-- [UBAH] Tema Merah -->
                    <input id="metode-{{ loop.index }}" name="metode_pengeluaran" type="radio" value="{{ metode }}" {% if loop.first %}checked{% endif %}
                           class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="metode-{{ loop.index }}" class="ml-3 block text-sm font-medium text-gray-700">{{ metode }}</label>
                </div>
                {% endfor %}
            </div>
        </div>

        <div id="kontak-pengeluaran-container" style="display:none;">
            <label for="kontak_pengeluaran" class="block text-sm font-medium text-gray-700">Nama Vendor/Pemasok</label>
            <!-- [UBAH] Tema Merah -->
            <input type="text" id="kontak_pengeluaran" name="kontak"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Masukkan nama vendor">
        </div>
        
        <div>
            <label for="deskripsi" class="block text-sm font-medium text-gray-700">Keterangan (opsional)</label>
            <!-- [UBAH] Tema Merah -->
            <textarea id="deskripsi" name="deskripsi" rows="3"
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Catatan tambahan..."></textarea>
        </div>
        <div>
            <!-- [UBAH] Tema Merah & Teks -->
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                ✅ Simpan Pengeluaran
            </button>
        </div>
    </form>

    <script>
        <!-- [UBAH] Variabel konsisten -->
        const kategoriData = {{ kategori_pengeluaran | tojson }};
        const kategoriSelect = document.getElementById('kategori');
        const subKategoriSelect = document.getElementById('sub_kategori');

        function updateSubKategori() {
            const selectedKategori = kategoriSelect.value;
            const subKategoriList = kategoriData[selectedKategori] || [];
            
            subKategoriSelect.innerHTML = ''; // Kosongkan
            
            subKategoriList.forEach(sub => {
                const option = document.createElement('option');
                option.value = sub;
                option.textContent = sub;
                subKategoriSelect.appendChild(option);
            });
        }
        
        kategoriSelect.addEventListener('change', updateSubKategori);
        
        updateSubKategori();

        document.addEventListener('DOMContentLoaded', function() {
            toggleKontakInput('metode_pengeluaran', 'kontak-pengeluaran-container');
        });
    </script>
</div>
"""

HTML_KELOLA_DATA = """
<div class="bg-white p-8 rounded-xl shadow-lg">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Kelola Data Transaksi</h2>
    
    <!-- Tabel Pemasukan -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Data Pemasukan</h3>
    <div class="overflow-x-auto rounded-lg border border-gray-200 mb-6">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sumber</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metode</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pelanggan</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for index, row in pemasukan_df.iterrows() %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ index }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(10, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Sumber'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Jumlah'] | rupiah }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Metode'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row.get('Kontak', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <a href="{{ url_for('hapus_page', tipe='pemasukan', index=index) }}" 
                           onclick="return confirm('Yakin ingin menghapus data ini? Aksi ini akan membuat jurnal pembalikan.')"
                           class="text-red-600 hover:text-red-900 font-medium">Hapus</a>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="7" class="px-4 py-3 text-center text-sm text-gray-500">Tidak ada data pemasukan.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Tabel Pengeluaran -->
    <!-- [UBAH] "Beban" -> "Pengeluaran" -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Data Pengeluaran</h3>
    <div class="overflow-x-auto rounded-lg border border-gray-200">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Kategori</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metode</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vendor</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for index, row in pengeluaran_df.iterrows() %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ index }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(10, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Kategori'] }} - {{ row['Sub Kategori'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Jumlah'] | rupiah }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Metode'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row.get('Kontak', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <a href="{{ url_for('hapus_page', tipe='pengeluaran', index=index) }}" 
                           onclick="return confirm('Yakin ingin menghapus data ini? Aksi ini akan membuat jurnal pembalikan.')"
                           class="text-red-600 hover:text-red-900 font-medium">Hapus</a>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="7" class="px-4 py-3 text-center text-sm text-gray-500">Tidak ada data pengeluaran.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
"""

HTML_LAPORAN = """
<div class="bg-white p-8 rounded-xl shadow-lg">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Laporan Keuangan</h2>
    
    <!-- Filter Tanggal -->
    <form method="POST" action="{{ url_for('laporan_page') }}" class="mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200 flex flex-wrap items-end gap-4">
        <div>
            <label for="mulai" class="block text-sm font-medium text-gray-700">Tanggal Mulai</label>
            <!-- [UBAH] Tema Merah -->
            <input type="date" id="mulai" name="mulai" value="{{ filter.mulai }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <div>
            <label for="akhir" class="block text-sm font-medium text-gray-700">Tanggal Akhir</label>
            <!-- [UBAH] Tema Merah -->
            <input type="date" id="akhir" name="akhir" value="{{ filter.akhir }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <!-- [UBAH] Tema Merah -->
        <button type="submit" class="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
            Terapkan Filter
        </button>
    </form>
    
    <!-- 1. Ringkasan -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Ringkasan</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <!-- [UBAH] Jaga warna finansial: Pemasukan = Hijau -->
        <div class="bg-green-50 p-4 rounded-lg border border-green-200">
            <div class="text-sm font-medium text-green-700">Total Pemasukan</div>
            <div class="text-2xl font-bold text-green-900">{{ ringkasan.total_pemasukan | rupiah }}</div>
        </div>
        <!-- [UBAH] Jaga warna finansial: Pengeluaran = Merah -->
        <div class="bg-red-50 p-4 rounded-lg border border-red-200">
            <div class="text-sm font-medium text-red-700">Total Pengeluaran</div>
            <div class="text-2xl font-bold text-red-900">{{ ringkasan.total_pengeluaran | rupiah }}</div>
        </div>
    </div>

    <!-- 2. Laba Rugi -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Laporan Laba Rugi</h3>
    <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-6">
        <div class="flow-root">
            <dl class="divide-y divide-gray-200">
                <div class="py-3 flex justify-between text-sm">
                    <dt class="text-gray-600">Pendapatan</dt>
                    <dd class="text-gray-900 font-medium">{{ laba_rugi.pendapatan | rupiah }}</dd>
                </div>
                <div class="py-3 flex justify-between text-sm">
                    <!-- [UBAH] "Beban" -> "Pengeluaran" -->
                    <dt class="text-gray-600">Total Pengeluaran (Beban)</dt>
                    <dd class="text-gray-900 font-medium">- {{ laba_rugi.beban | rupiah }}</dd>
                </div>
                <div class="py-3 flex justify-between text-base font-semibold">
                    <dt class="text-gray-900">Laba / Rugi</dt>
                    <!-- [UBAH] Jaga warna finansial -->
                    <dd class="{% if laba_rugi.laba_rugi >= 0 %}text-green-700{% else %}text-red-700{% endif %}">{{ laba_rugi.laba_rugi | rupiah }}</dd>
                </div>
            </dl>
        </div>
    </div>

    <!-- 3. Neraca -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Neraca (Posisi Keuangan s/d {{ filter.akhir }})</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <!-- Sisi Aktiva -->
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Aktiva (Harta)</h4>
            <dl class="divide-y divide-gray-200">
                <div class="py-2 flex justify-between text-sm">
                    <dt class="text-gray-600">Total Aktiva</dt>
                    <dd class="text-gray-900 font-medium">{{ neraca.aktiva | rupiah }}</dd>
                </div>
            </dl>
        </div>
        <!-- Sisi Pasiva -->
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Pasiva (Kewajiban + Ekuitas)</h4>
            <dl class="divide-y divide-gray-200">
                <div class="py-2 flex justify-between text-sm">
                    <dt class="text-gray-600">Kewajiban (Utang)</dt>
                    <dd class="text-gray-900 font-medium">{{ neraca.kewajiban | rupiah }}</dd>
                </div>
                <div class="py-2 flex justify-between text-sm">
                    <dt class="text-gray-600">Ekuitas (Modal/Laba Ditahan)</dt>
                    <dd class="text-gray-900 font-medium">{{ neraca.ekuitas | rupiah }}</dd>
                </div>
                <div class="py-2 flex justify-between text-sm font-semibold">
                    <dt class="text-gray-900">Total Pasiva</dt>
                    <dd class="text-gray-900">{{ (neraca.kewajiban + neraca.ekuitas) | rupiah }}</dd>
                </div>
            </dl>
        </div>
    </div>

    <!-- (Req 3) Buku Besar Pembantu -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Buku Besar Pembantu (s/d {{ filter.akhir }})</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <!-- BBP Piutang -->
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Piutang Dagang</h4>
            <dl class="divide-y divide-gray-200">
                {% for kontak, saldo in buku_pembantu_piutang.items() %}
                    {% if saldo != 0 %}
                    <div class="py-2 flex justify-between text-sm">
                        <dt class="text-gray-600">{{ kontak }}</dt>
                        <dd class="text-gray-900 font-medium">{{ saldo | rupiah }}</dd>
                    </div>
                    {% endif %}
                {% else %}
                    <div class="py-2 text-sm text-gray-500">Tidak ada piutang.</div>
                {% endfor %}
            </dl>
        </div>
        <!-- BBP Utang -->
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Utang Dagang</h4>
            <dl class="divide-y divide-gray-200">
                {% for kontak, saldo in buku_pembantu_utang.items() %}
                    {% if saldo != 0 %}
                    <div class="py-2 flex justify-between text-sm">
                        <dt class="text-gray-600">{{ kontak }}</dt>
                        <dd class="text-gray-900 font-medium">{{ saldo | rupiah }}</dd>
                    </div>
                    {% endif %}
                {% else %}
                    <div class="py-2 text-sm text-gray-500">Tidak ada utang.</div>
                {% endfor %}
            </dl>
        </div>
    </div>
    <!-- Akhir Perubahan (Req 3) -->


    <!-- 4. Jurnal Umum -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Jurnal Umum (Periode {{ filter.mulai }} s/d {{ filter.akhir }})</h3>
    <div class="overflow-x-auto rounded-lg border border-gray-200 mb-6">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Akun</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Keterangan</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Kontak</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Debit</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Kredit</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for index, row in jurnal_df.iterrows() %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(19, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm {% if row['Debit'] > 0 %}pl-6{% else %}pl-10{% endif %} text-gray-900">{{ row['Akun'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Keterangan'] | truncate(30, True) }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row.get('Kontak', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{% if row['Debit'] > 0 %}{{ row['Debit'] | rupiah }}{% endif %}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{% if row['Kredit'] > 0 %}{{ row['Kredit'] | rupiah }}{% endif %}</td>
                </tr>
                {% else %}
                <tr><td colspan="6" class="px-4 py-3 text-center text-sm text-gray-500">Tidak ada data jurnal.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- 5. Buku Besar -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Buku Besar (Periode {{ filter.mulai }} s/d {{ filter.akhir }})</h3>
    <div class="space-y-4">
        {% for akun, data in buku_besar.items() %}
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Akun: {{ akun }}</h4>
            <div class="overflow-x-auto rounded-md border border-gray-100">
                <table class="min-w-full divide-y divide-gray-200">
                     <thead class="bg-gray-100">
                        <tr>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tanggal</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Keterangan</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Kontak</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Debit</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Kredit</th>
                            <th class="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Saldo</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {% for row in data.itertuples() %}
                        <tr>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Tanggal | string | truncate(10, True, '') }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Keterangan | truncate(30, True) }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Kontak }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{% if row.Debit > 0 %}{{ row.Debit | rupiah }}{% endif %}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{% if row.Kredit > 0 %}{{ row.Kredit | rupiah }}{% endif %}</td>
                            <td class.px-3 py-2 whitespace-nowrap text-sm text-gray-900 font-medium">{{ row.Saldo | rupiah }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% else %}
        <p class="text-sm text-gray-500">Tidak ada data untuk buku besar.</p>
        {% endfor %}
    </div>
    
</div>
"""


# ---------------- RUTE FLASK (Dengan Perbaikan) ----------------

@app.route("/")
@login_required
def index_page():
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_INDEX)
    return render_template_string(full_html, title="Beranda")

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get('logged_in'):
        return redirect(url_for('index_page'))
        
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        mode = request.form.get("mode")
        
        if not username or not password:
            flash("Username dan password tidak boleh kosong.", "danger")
            return redirect(url_for('login_page'))

        if mode == "Daftar":
            if register_user(username, password):
                flash("Akun berhasil dibuat. Silakan login.", "success")
            else:
                flash("Username sudah digunakan.", "danger")
            return redirect(url_for('login_page'))
        
        elif mode == "Login":
            if validate_login(username, password):
                session['logged_in'] = True
                session['username'] = username
                flash(f"Login berhasil! Selamat datang, {username}.", "success")
                return redirect(url_for('index_page'))
            else:
                flash("Username atau password salah.", "danger")
                return redirect(url_for('login_page'))

    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LOGIN)
    return render_template_string(full_html, title="Login")

@app.route("/logout")
def logout_page():
    session.clear()
    flash("Anda telah berhasil logout.", "success")
    return redirect(url_for('login_page'))

@app.route("/pemasukan", methods=["GET", "POST"])
@login_required
def pemasukan_page():
    username = session['username']
    if request.method == "POST":
        try:
            tanggal = request.form.get("tanggal")
            waktu = datetime.combine(datetime.strptime(tanggal, "%Y-%m-%d").date(), datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
            
            sumber = request.form.get("sumber")
            
            jumlah_str = request.form.get("jumlah", "0").replace(".", "")
            jumlah = float(jumlah_str)
            
            metode = request.form.get("metode_pemasukan") 
            deskripsi = request.form.get("deskripsi", "")
            
            kontak = request.form.get("kontak", "").strip()
            
            if (metode == "Piutang" or metode == "Pelunasan Piutang") and not kontak:
                flash("Nama Pelanggan wajib diisi untuk transaksi Piutang.", "danger")
                return redirect(url_for('pemasukan_page'))

            if jumlah <= 0:
                flash("Jumlah harus lebih dari 0.", "danger")
                return redirect(url_for('pemasukan_page'))
            
            data = {
                "Tanggal": waktu, "Sumber": sumber, "Jumlah": jumlah,
                "Metode": metode, "Keterangan": deskripsi, "Username": username, "Kontak": kontak
            }
            append_data(data, "pemasukan.csv", username)
            
            akun_debit = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang", "Pelunasan Piutang": "Kas"}.get(metode, "Kas")
            akun_kredit = "Pendapatan" if metode != "Pelunasan Piutang" else "Piutang Dagang"
            
            jurnal = buat_jurnal(waktu, akun_debit, akun_kredit, jumlah, f"{sumber} - {deskripsi}", kontak)
            for j in jurnal:
                append_data(j, "jurnal.csv", username)
                
            flash("Pemasukan berhasil disimpan.", "success")
            return redirect(url_for('pemasukan_page'))
            
        except Exception as e:
            flash(f"Terjadi error: {e}", "danger")
            
    today = datetime.now().strftime("%Y-%m-%d")
    
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PEMASUKAN)
    return render_template_string(full_html, title="Pemasukan", kategori_pemasukan=kategori_pemasukan, today=today)


@app.route("/pengeluaran", methods=["GET", "POST"])
@login_required
def pengeluaran_page():
    username = session['username']
    if request.method == "POST":
        try:
            tanggal = request.form.get("tanggal")
            waktu = datetime.combine(datetime.strptime(tanggal, "%Y-%m-%d").date(), datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
            
            kategori = request.form.get("kategori")
            sub_kategori = request.form.get("sub_kategori")
            
            jumlah_str = request.form.get("jumlah", "0").replace(".", "")
            jumlah = float(jumlah_str)

            metode = request.form.get("metode_pengeluaran")
            deskripsi = request.form.get("deskripsi", "")
            
            kontak = request.form.get("kontak", "").strip()

            if (metode == "Utang" or metode == "Pelunasan Utang") and not kontak:
                flash("Nama Vendor wajib diisi untuk transaksi Utang.", "danger")
                return redirect(url_for('pengeluaran_page'))
            
            if jumlah <= 0:
                flash("Jumlah harus lebih dari 0.", "danger")
                return redirect(url_for('pengeluaran_page'))
            
            data = {
                "Tanggal": waktu, "Kategori": kategori, "Sub Kategori": sub_kategori,
                "Jumlah": jumlah, "Keterangan": deskripsi, "Metode": metode, "Username": username, "Kontak": kontak
            }
            append_data(data, "pengeluaran.csv", username)
            
            akun_kredit = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang", "Pelunasan Utang": "Kas"}.get(metode, "Kas")
            akun_debit = sub_kategori if metode != "Pelunasan Utang" else "Utang Dagang"
            
            jurnal = buat_jurnal(waktu, akun_debit, akun_kredit, jumlah, f"{kategori} - {deskripsi}", kontak)
            for j in jurnal:
                append_data(j, "jurnal.csv", username)

            # [UBAH] "Beban" -> "Pengeluaran"
            flash("Pengeluaran berhasil disimpan.", "success")
            return redirect(url_for('pengeluaran_page'))

        except Exception as e:
            flash(f"Terjadi error: {e}", "danger")
            
    today = datetime.now().strftime("%Y-%m-%d")
    
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PENGELUARAN)
    # [UBAH] "Beban" -> "Pengeluaran" & var konsisten
    return render_template_string(full_html, title="Pengeluaran", kategori_pengeluaran=kategori_pengeluaran, today=today)


@app.route("/kelola")
@login_required
def kelola_page():
    username = session['username']
    pemasukan_df = load_data("pemasukan.csv", username)
    if not pemasukan_df.empty:
        pemasukan_df = pemasukan_df.sort_values(by="Tanggal", ascending=False)
        
    pengeluaran_df = load_data("pengeluaran.csv", username)
    if not pengeluaran_df.empty:
        pengeluaran_df = pengeluaran_df.sort_values(by="Tanggal", ascending=False)
    
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_KELOLA_DATA)
    return render_template_string(full_html, title="Kelola Data", 
                                  pemasukan_df=pemasukan_df, pengeluaran_df=pengeluaran_df)

@app.route("/hapus/<string:tipe>/<int:index>")
@login_required
def hapus_page(tipe, index):
    username = session['username']
    if tipe not in ['pemasukan', 'pengeluaran']:
        flash("Tipe transaksi tidak valid.", "danger")
        return redirect(url_for('kelola_page'))
        
    if hapus_transaksi(tipe, index, username):
        flash(f"Data {tipe} ID {index} berhasil dihapus dan jurnal pembalikan dibuat.", "success")
    else:
        flash(f"Gagal menghapus data {tipe} ID {index}. Mungkin index tidak ditemukan.", "danger")
        
    return redirect(url_for('kelola_page'))


@app.route("/laporan", methods=["GET", "POST"])
@login_required
def laporan_page():
    username = session['username']
    
    if request.method == "POST":
        mulai_str = request.form.get("mulai")
        akhir_str = request.form.get("akhir")
    else:
        mulai_str = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        akhir_str = datetime.now().strftime("%Y-%m-%d")
        
    filter_tanggal = {"mulai": mulai_str, "akhir": akhir_str}
    
    try:
        mulai_dt = pd.to_datetime(mulai_str)
        akhir_dt = pd.to_datetime(akhir_str) + pd.Timedelta(days=1)
    except ValueError:
        flash("Format tanggal tidak valid.", "danger")
        empty_df = pd.DataFrame(columns=["Tanggal", "Akun", "Debit", "Kredit", "Keterangan", "Kontak"])
        full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LAPORAN)
        return render_template_string(
            full_html, title="Laporan", filter=filter_tanggal,
            ringkasan={"total_pemasukan": 0, "total_pengeluaran": 0},
            laba_rugi={"pendapatan": 0, "beban": 0, "laba_rugi": 0},
            neraca={"aktiva": 0, "kewajiban": 0, "ekuitas": 0},
            buku_pembantu_piutang={}, buku_pembantu_utang={},
            jurnal_df=empty_df, buku_besar={}
        )

    # Load data
    pemasukan_df = load_data("pemasukan.csv", username)
    pengeluaran_df = load_data("pengeluaran.csv", username)
    jurnal_df = load_data("jurnal.csv", username)

    for df in [pemasukan_df, pengeluaran_df, jurnal_df]:
        if not df.empty and "Tanggal" in df.columns:
            df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors='coerce')
            df.dropna(subset=['Tanggal'], inplace=True)
    
    # --- Filter Data ---
    pemasukan_df_f = pemasukan_df[(pemasukan_df['Tanggal'] >= mulai_dt) & (pemasukan_df['Tanggal'] < akhir_dt)] if not pemasukan_df.empty else pd.DataFrame(columns=pemasukan_df.columns)
    pengeluaran_df_f = pengeluaran_df[(pengeluaran_df['Tanggal'] >= mulai_dt) & (pengeluaran_df['Tanggal'] < akhir_dt)] if not pengeluaran_df.empty else pd.DataFrame(columns=pengeluaran_df.columns)
    jurnal_df_f = jurnal_df[(jurnal_df['Tanggal'] >= mulai_dt) & (jurnal_df['Tanggal'] < akhir_dt)] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    jurnal_total = jurnal_df[jurnal_df['Tanggal'] < akhir_dt] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    # --- Perhitungan ---
    ringkasan = {
        "total_pemasukan": pemasukan_df_f['Jumlah'].sum() if not pemasukan_df_f.empty else 0,
        "total_pengeluaran": pengeluaran_df_f['Jumlah'].sum() if not pengeluaran_df_f.empty else 0
    }

    pendapatan = 0
    beban = 0
    if not jurnal_df_f.empty:
        pendapatan = jurnal_df_f[jurnal_df_f['Akun'].str.contains("Pendapatan", na=False)]['Kredit'].sum()
        # [UBAH] var konsisten
        beban_akun = list(kategori_pengeluaran.keys())
        for subs in kategori_pengeluaran.values():
            beban_akun.extend(subs)
        beban = jurnal_df_f[jurnal_df_f['Akun'].isin(beban_akun)]['Debit'].sum()
        
    laba_rugi_data = {"pendapatan": pendapatan, "beban": beban, "laba_rugi": pendapatan - beban}

    aktiva, kewajiban, ekuitas = 0, 0, 0
    if not jurnal_total.empty:
        aktiva_akun = ['Kas', 'Bank', 'Piutang Dagang']
        kewajiban_akun = ['Utang Dagang']
        
        aktiva = jurnal_total[jurnal_total['Akun'].isin(aktiva_akun)]['Debit'].sum() - \
                 jurnal_total[jurnal_total['Akun'].isin(aktiva_akun)]['Kredit'].sum()
        kewajiban = jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Kredit'].sum() - \
                    jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Debit'].sum()
        
        pendapatan_total = jurnal_total[jurnal_total['Akun'].str.contains("Pendapatan", na=False)]['Kredit'].sum()
        # [UBAH] var konsisten
        beban_akun_total = list(kategori_pengeluaran.keys())
        for subs in kategori_pengeluaran.values():
            beban_akun_total.extend(subs)
        beban_total = jurnal_total[jurnal_total['Akun'].isin(beban_akun_total)]['Debit'].sum()
        ekuitas = pendapatan_total - beban_total

    neraca_data = {"aktiva": aktiva, "kewajiban": kewajiban, "ekuitas": ekuitas}

    buku_pembantu_piutang = {}
    buku_pembantu_utang = {}
    if not jurnal_total.empty:
        # Piutang
        df_piutang = jurnal_total[(jurnal_total['Akun'] == 'Piutang Dagang') & (jurnal_total['Kontak'].notna()) & (jurnal_total['Kontak'] != '')].copy()
        if not df_piutang.empty:
            df_piutang['Saldo'] = df_piutang['Debit'] - df_piutang['Kredit']
            buku_pembantu_piutang = df_piutang.groupby('Kontak')['Saldo'].sum().to_dict()

        # Utang
        df_utang = jurnal_total[(jurnal_total['Akun'] == 'Utang Dagang') & (jurnal_total['Kontak'].notna()) & (jurnal_total['Kontak'] != '')].copy()
        if not df_utang.empty:
            df_utang['Saldo'] = df_utang['Kredit'] - df_utang['Debit']
            buku_pembantu_utang = df_utang.groupby('Kontak')['Saldo'].sum().to_dict()

    buku_besar_data = {}
    if not jurnal_df_f.empty:
        jurnal_df_f['Kontak'] = jurnal_df_f['Kontak'].fillna('')
        akun_list = sorted(jurnal_df_f['Akun'].unique())
        for akun in akun_list:
            df_akun = jurnal_df_f[jurnal_df_f['Akun'] == akun].copy().sort_values("Tanggal")
            saldo = 0
            saldos = []
            if not jurnal_total.empty:
                saldo_awal_df = jurnal_total[(jurnal_total['Akun'] == akun) & (jurnal_total['Tanggal'] < mulai_dt)]
                if not saldo_awal_df.empty:
                    saldo = saldo_awal_df['Debit'].sum() - saldo_awal_df['Kredit'].sum()
            
            saldos.append(saldo)
            
            for _, row in df_akun.iterrows():
                saldo += (row['Debit'] - row['Kredit'])
                saldos.append(saldo)
            
            saldo_awal_row = pd.DataFrame([{
                'Tanggal': mulai_dt - pd.Timedelta(days=1), 
                'Keterangan': 'Saldo Awal', 
                'Kontak': '', 
                'Debit': 0, 
                'Kredit': 0, 
                'Saldo': saldos[0] 
            }])
            
            df_akun['Saldo'] = saldos[1:] 
            
            buku_besar_data[akun] = pd.concat([saldo_awal_row, df_akun], ignore_index=True)


    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LAPORAN)
    return render_template_string(
        full_html, 
        title="Laporan",
        filter=filter_tanggal,
        ringkasan=ringkasan,
        laba_rugi=laba_rugi_data,
        neraca=neraca_data,
        buku_pembantu_piutang=buku_pembantu_piutang,
        buku_pembantu_utang=buku_pembantu_utang,
        jurnal_df=jurnal_df_f.sort_values(by="Tanggal") if not jurnal_df_f.empty else pd.DataFrame(),
        buku_besar=buku_besar_data
    )
# --- Akhir Perubahan ---


# ---------------- Menjalankan Aplikasi (LOKAL) ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)