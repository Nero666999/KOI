import os
import pandas as pd
from datetime import datetime
from functools import wraps
import locale 
from supabase import create_client, Client

# Impor library Flask
from flask import (
    Flask, 
    render_template_string, # <-- KITA TETAP PAKAI INI
    request, 
    redirect, 
    url_for, 
    session, 
    flash
)

# --- KONEKSI KE SUPABASE ---
# INI PUNYAMU, SUDAH BENAR
SUPABASE_URL = "https://asweqitjjbepoxwpscsz.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFzd2VxaXRqamJlcG94d3BzY3N6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIzMzg3NzMsImV4cCI6MjA3NzkxNDc3M30.oihrg9Pz0qa0LS5DIJzM2itIbtG0oh__PlOqx4nd2To" 

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("--- BERHASIL KONEK KE SUPABASE ---") 
except Exception as e:
    print(f"--- GAGAL KONEK KE SUPABASE: {e} ---")
# --- Akhir Koneksi ---


# --- [DIHAPUS] Path Absolut (TIDAK DIPAKAI LAGI) ---
# APP_DIR = os.path.dirname(os.path.abspath(__file__))

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
    "Penjualan": ["Penjualan - Kohaku", "Penjualan - Shusui", "Penjualan - Tancho", "Penjualan - Kumpay"],
    "Pendapatan Lain": ["Pendapatan - Jasa", "Pendapatan - Lain-lain"]
}

# --- [DIHAPUS] columns_map tidak dipakai lagi ---

# ---------------- Helper Functions (DIGANTI TOTAL) ----------------

# --- [DIHAPUS] Fungsi Auth CSV (hash_password, load_user_accounts, dll) ---
# --- [DIHAPUS] Fungsi CSV (get_user_file, load_data, save_data, append_data, buat_jurnal, hapus_transaksi) ---

# --- [BARU] Fungsi helper untuk Supabase ---
def load_data_from_db(tabel, user_id):
    """Mengambil data dari tabel Supabase dan mengubahnya jadi DataFrame."""
    try:
        # "SELECT * FROM tabel WHERE user_id = user_id"
        response = supabase.from_(tabel).select("*").eq("user_id", user_id).execute()
        
        # [FIX V4] Jika GAGAL, 'execute()' akan 'raise Exception'
        
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Error load_data_from_db ({tabel}): {e}")
        flash(f"Gagal mengambil data dari DB: {e}", "danger")
        return pd.DataFrame() # Kembalikan DataFrame kosong jika error

def append_data_to_db(tabel, data, user_id):
    """Menyimpan data (dictionary) ke tabel Supabase."""
    try:
        data['user_id'] = user_id # "Suntikkan" user_id ke data
        response = supabase.from_(tabel).insert(data).execute()
        
        # [FIX V4] Jika GAGAL, 'execute()' akan 'raise Exception'
            
    except Exception as e:
        # Tampilkan error di terminal
        print(f"Error append_data_to_db ({tabel}): {e}")
        # Tampilkan error ke user
        flash(f"Gagal menyimpan data ke DB: {e}", "danger")
        # 'raise' lagi agar rute bisa menangkapnya
        raise e 

def buat_jurnal_batch(jurnal_entries, user_id):
    """Menyimpan beberapa entri jurnal sekaligus ke Supabase."""
    try:
        # "Suntikkan" user_id ke setiap entri
        for entry in jurnal_entries:
            entry['user_id'] = user_id
        
        response = supabase.from_("jurnal").insert(jurnal_entries).execute()
        
        # [FIX V4] Jika GAGAL, 'execute()' akan 'raise Exception'
            
    except Exception as e:
        print(f"Error buat_jurnal_batch: {e}")
        flash(f"Gagal menyimpan jurnal ke DB: {e}", "danger")
        raise e

def hapus_transaksi_db(tabel, db_id, user_id):
    """Menghapus transaksi dari Supabase dan membuat jurnal pembalikan."""
    try:
        # 1. Ambil data yang mau dihapus (untuk bikin jurnal pembalikan)
        #    Pastikan hanya user yang benar yang bisa ambil
        response = supabase.from_(tabel).select("*").eq("id", db_id).eq("user_id", user_id).single().execute()
        
        # [FIX V4] Jika GAGAL, 'execute()' akan 'raise Exception'
        
        transaksi = response.data
        
        # 2. Hapus data aslinya
        #    (Satpam RLS akan cek 'user_id' lagi di sini)
        delete_response = supabase.from_(tabel).delete().eq("id", db_id).execute()
        
        # [FIX V4] Jika GAGAL, 'execute()' akan 'raise Exception'

        # 3. Buat Jurnal Pembalikan (logika sama kayak dulu)
        waktu_hapus = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        keterangan_asli = transaksi.get('Keterangan', '')
        jumlah_transaksi = float(transaksi['Jumlah'])
        metode_transaksi = transaksi['Metode']
        kontak = transaksi.get('Kontak', '')
        
        jurnal_pembalikan_entries = []
        
        if tabel == "pemasukan":
            sub_sumber = transaksi.get('Sub_Sumber', 'Lain-lain') # Ambil sub sumber (nama kolom DB)
            keterangan_batal = f"Pembatalan: {transaksi.get('Sumber', '')} - {sub_sumber}"
            
            if metode_transaksi == "Pelunasan Piutang":
                # Balik jurnal pelunasan
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": "Piutang Dagang", "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": kontak},
                    {"Tanggal": waktu_hapus, "Akun": "Kas", "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": ""}
                ]
            else:
                # Balik jurnal pendapatan
                akun_debit_pembalikan = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang"}.get(metode_transaksi, "Kas")
                akun_kredit_asli = sub_sumber 
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": akun_kredit_asli, "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": ""},
                    {"Tanggal": waktu_hapus, "Akun": akun_debit_pembalikan, "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": kontak if akun_debit_pembalikan == "Piutang Dagang" else ""}
                ]
        
        elif tabel == "pengeluaran":
            kategori = transaksi.get('Kategori', '')
            sub_kategori = transaksi.get('Sub_Kategori', 'Beban Lain') # Nama kolom DB
            keterangan_batal = f"Pembatalan: {kategori} - {sub_kategori}"

            if metode_transaksi == "Pelunasan Utang":
                # Balik jurnal pelunasan utang
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": "Kas", "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": ""},
                    {"Tanggal": waktu_hapus, "Akun": "Utang Dagang", "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": kontak}
                ]
            else:
                # Balik jurnal beban
                akun_kredit_pembalikan = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang"}.get(metode_transaksi, "Kas")
                akun_debit_asli = sub_kategori
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": akun_kredit_pembalikan, "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": kontak if akun_kredit_pembalikan == "Utang Dagang" else ""},
                    {"Tanggal": waktu_hapus, "Akun": akun_debit_asli, "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": ""}
                ]
        else:
            return False
        
        # 4. Simpan jurnal pembalikan ke DB
        buat_jurnal_batch(jurnal_pembalikan_entries, session['user_id']) # Ambil user_id dari session
        return True
        
    except Exception as e:
        print(f"Error hapus_transaksi_db: {e}")
        flash(f"Gagal menghapus data: {e}", "danger")
        return False
# --- Akhir Helper Functions ---
    

# ---------------- Decorator (Sudah Benar) ----------------
# --- Ini adalah "Satpam" Tiket Masuknya ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Cek dulu, user ini punya 'tiket masuk' di session-nya gak?
        if 'access_token' not in session:
            session.clear()
            flash("Sesi tidak valid. Harap login ulang.", "danger")
            return redirect(url_for('login_page'))
        
        # 2. Jika punya, tunjukkan tiket itu ke Supabase SETIAP BUKA HALAMAN
        try:
            supabase.auth.set_session(
                session['access_token'], 
                session.get('refresh_token')
            )
            # Coba ambil data user untuk validasi token
            response = supabase.auth.get_user()
            
            if not response or not response.user:
                raise Exception("Token tidak valid atau sudah kedaluwarsa.")
                
            # Pastikan user_id juga ada di session
            if 'user_id' not in session:
                 session['user_id'] = response.user.id
            if 'username' not in session:
                 session['username'] = response.user.email
            if 'logged_in' not in session:
                 session['logged_in'] = True

        except Exception as e:
            # Gagal nunjukin tiket (mungkin udah expired)
            print(f"Gagal set session di decorator: {e}")
            session.clear()
            flash("Sesi Anda telah berakhir. Harap login ulang.", "danger")
            return redirect(url_for('login_page'))
        
        # 3. Tiket valid! Lanjut ke halaman (misal: /pemasukan)
        return f(*args, **kwargs)
    return decorated_function
# --- Akhir Perubahan Decorator ---

# ---------------- KUMPULAN TEMPLATE HTML ----------------
# (Semua HTML tidak diubah, kecuali KELOLA DATA & LAPORAN)

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
                    <a href="{{ url_for('index_page') }}" class="flex-shrink-0 flex items-center text-xl font-bold text-red-700">
                         Koilume (Lokal)
                    </a>
                </div>
                <div class="flex items-center">
                    {% if session.logged_in %}
                        <!-- session['username'] sekarang berisi email -->
                        <span class="text-gray-700 mr-4">Halo, {{ session.username }}!</span>
                        <a href="{{ url_for('index_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Beranda</a>
                        <a href="{{ url_for('pemasukan_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Pemasukan</a>
                        <a href="{{ url_for('pengeluaran_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Pengeluaran</a>
                        <a href="{{ url_for('kelola_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Kelola Data</a>
                        <a href="{{ url_for('laporan_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Laporan</a>
                        <a href="{{ url_for('logout_page') }}" class="ml-4 px-3 py-2 rounded-md text-sm font-medium text-red-600 bg-red-100 hover:bg-red-200">Logout</a>
                    {% else %}
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
                Login atau Daftar Akun (via Supabase)
            </h2>
        </div>
        <form class="mt-8 space-y-6" action="{{ url_for('login_page') }}" method="POST">
            <div class="rounded-md shadow-sm -space-y-px">
                <div>
                    <label for="email" class="sr-only">Email</label>
                    <input id="email" name="email" type="email" autocomplete="email" required 
                           class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" 
                           placeholder="Alamat Email">
                </div>
                <div>
                    <label for="password" class="sr-only">Kata Sandi</label>
                    <input id="password" name="password" type="password" autocomplete="current-password" required 
                           class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" 
                           placeholder="Kata Sandi">
                </div>
            </div>

            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <input id="mode-login" name="mode" type="radio" value="Login" checked class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="mode-login" class="ml-2 block text-sm text-gray-900"> Login </label>
                </div>
                <div class="flex items-center">
                    <input id="mode-daftar" name="mode" type="radio" value="Daftar" class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="mode-daftar" class="ml-2 block text-sm text-gray-900"> Daftar </label>
                </div>
            </div>

            <div>
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
    <p class="text-gray-700 text-lg">Ini adalah aplikasi akuntansi Koilume versi web.</p>
    <ul class="list-disc list-inside mt-4 text-gray-600">
        <li>Gunakan menu <b class="text-red-600">Pemasukan</b> untuk mencatat pendapatan.</li>
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
            <input type="date" id="tanggal" name="tanggal" value="{{ today }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        
        <!-- Dropdown Kategori (Sumber) -->
        <div>
            <label for="sumber" class="block text-sm font-medium text-gray-700">Kategori Pemasukan</label>
            <select id="sumber" name="sumber" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                {% for sumber in kategori_pemasukan.keys() %}
                <option value="{{ sumber }}">{{ sumber }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- Dropdown Sub-Kategori (Sub Sumber) -->
        <div>
            <label for="sub_sumber" class="block text-sm font-medium text-gray-700">Akun Pemasukan</label>
            <select id="sub_sumber" name="sub_sumber" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                <!-- Opsi akan diisi oleh JavaScript -->
            </select>
        </div>

        <div>
            <label for="jumlah" class="block text-sm font-medium text-gray-700">Jumlah (Rp)</label>
            <input type="text" id="jumlah" name="jumlah" min="0" required inputmode="numeric"
                   onkeyup="formatRupiah(this)"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Contoh: 1.000.000">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Metode Penerimaan</label>
            <div class="mt-2 space-y-2" onchange="toggleKontakInput('metode_pemasukan', 'kontak-pemasukan-container')">
                {% for metode in ['Tunai', 'Transfer', 'Piutang', 'Pelunasan Piutang'] %}
                <div class="flex items-center">
                    <input id="metode-{{ loop.index }}" name="metode_pemasukan" type="radio" value="{{ metode }}" {% if loop.first %}checked{% endif %}
                           class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="metode-{{ loop.index }}" class="ml-3 block text-sm font-medium text-gray-700">{{ metode }}</label>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div id="kontak-pemasukan-container" style="display:none;">
            <label for="kontak_pemasukan" class="block text-sm font-medium text-gray-700">Nama Pelanggan</label>
            <input type="text" id="kontak_pemasukan" name="kontak"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Masukkan nama pelanggan">
        </div>
        
        <div>
            <label for="deskripsi" class="block text-sm font-medium text-gray-700">Keterangan (opsional)</label>
            <textarea id="deskripsi" name="deskripsi" rows="3"
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Catatan tambahan..."></textarea>
        </div>
        <div>
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                ✅ Simpan Pemasukan
            </button>
        </div>
    </form>
    
    <!-- Script untuk dropdown dinamis Pemasukan -->
    <script>
        const kategoriPemasukanData = {{ kategori_pemasukan | tojson }};
        const sumberSelect = document.getElementById('sumber');
        const subSumberSelect = document.getElementById('sub_sumber');

        function updateSubSumber() {
            const selectedSumber = sumberSelect.value;
            const subSumberList = kategoriPemasukanData[selectedSumber] || [];
            
            subSumberSelect.innerHTML = ''; // Kosongkan
            
            subSumberList.forEach(sub => {
                const option = document.createElement('option');
                option.value = sub;
                option.textContent = sub;
                subSumberSelect.appendChild(option);
            });
        }
        
        sumberSelect.addEventListener('change', updateSubSumber);
        
        // Panggil sekali saat load
        updateSubSumber();

        // Panggil fungsi toggle saat halaman load
        document.addEventListener('DOMContentLoaded', function() {
            toggleKontakInput('metode_pemasukan', 'kontak-pemasukan-container');
        });
    </script>
</div>
"""

HTML_PENGELUARAN = """
<div class="bg-white p-8 rounded-xl shadow-lg max-w-2xl mx-auto">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Tambah Pengeluaran</h2>
    <form action="{{ url_for('pengeluaran_page') }}" method="POST" class="space-y-4">
        <div>
            <label for="tanggal" class="block text-sm font-medium text-gray-700">Tanggal</label>
            <input type="date" id="tanggal" name="tanggal" value="{{ today }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <div>
            <label for="kategori" class="block text-sm font-medium text-gray-700">Kategori Pengeluaran</label>
            <select id="kategori" name="kategori" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                {% for kategori in kategori_pengeluaran.keys() %}
                <option value="{{ kategori }}">{{ kategori }}</option>
                {% endfor %}
            </select>
        </div>
        <div>
            <label for="sub_kategori" class="block text-sm font-medium text-gray-700">Sub Kategori (Akun)</label>
            <select id="sub_kategori" name="sub_kategori" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                <!-- Opsi akan diisi oleh JavaScript -->
            </select>
        </div>
        <div>
            <label for="jumlah" class="block text-sm font-medium text-gray-700">Jumlah (Rp)</label>
            <input type="text" id="jumlah" name="jumlah" min="0" required inputmode="numeric"
                   onkeyup="formatRupiah(this)"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Contoh: 150.000">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700">Metode Pembayaran</label>
            <div class="mt-2 space-y-2" onchange="toggleKontakInput('metode_pengeluaran', 'kontak-pengeluaran-container')">
                {% for metode in ['Tunai', 'Transfer', 'Utang', 'Pelunasan Utang'] %}
                <div class="flex items-center">
                    <input id="metode-{{ loop.index }}" name="metode_pengeluaran" type="radio" value="{{ metode }}" {% if loop.first %}checked{% endif %}
                           class="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300">
                    <label for="metode-{{ loop.index }}" class="ml-3 block text-sm font-medium text-gray-700">{{ metode }}</label>
                </div>
                {% endfor %}
            </div>
        </div>

        <div id="kontak-pengeluaran-container" style="display:none;">
            <label for="kontak_pengeluaran" class="block text-sm font-medium text-gray-700">Nama Vendor/Pemasok</label>
            <input type="text" id="kontak_pengeluaran" name="kontak"
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Masukkan nama vendor">
        </div>
        
        <div>
            <label for="deskripsi" class="block text-sm font-medium text-gray-700">Keterangan (opsional)</label>
            <textarea id="deskripsi" name="deskripsi" rows="3"
                      class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm" placeholder="Catatan tambahan..."></textarea>
        </div>
        <div>
            <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
                ✅ Simpan Pengeluaran
            </button>
        </div>
    </form>

    <script>
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

# --- [PERBAIKAN] HTML Kelola Data dirombak ---
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
                    <!-- Kolom Baru -->
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sub Sumber</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metode</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pelanggan</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                <!-- [PERBAIKAN] Ganti .iterrows() -> loop list biasa -->
                {% for row in pemasukan_df %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['id'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(10, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Sumber'] }}</td>
                    <!-- [PERBAIKAN] Nama kolom DB pakai underscore -->
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row.get('Sub_Sumber', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Jumlah'] | rupiah }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Metode'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row.get('Kontak', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <a href="{{ url_for('hapus_page', tipe='pemasukan', db_id=row['id']) }}" 
                           onclick="return confirm('Yakin ingin menghapus data ini? Aksi ini akan membuat jurnal pembalikan.')"
                           class="text-red-600 hover:text-red-900 font-medium">Hapus</a>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="8" class="px-4 py-3 text-center text-sm text-gray-500">Tidak ada data pemasukan.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Tabel Pengeluaran -->
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
                <!-- [PERBAIKAN] Ganti .iterrows() -> loop list biasa -->
                {% for row in pengeluaran_df %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['id'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(10, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Kategori'] }} - {{ row['Sub_Kategori'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Jumlah'] | rupiah }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Metode'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row.get('Kontak', '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm">
                        <a href="{{ url_for('hapus_page', tipe='pengeluaran', db_id=row['id']) }}" 
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
# --- Akhir Perubahan ---

HTML_LAPORAN = """
<div class="bg-white p-8 rounded-xl shadow-lg">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Laporan Keuangan</h2>
    
    <!-- Filter Tanggal -->
    <form method="POST" action="{{ url_for('laporan_page') }}" class="mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200 flex flex-wrap items-end gap-4">
        <div>
            <label for="mulai" class="block text-sm font-medium text-gray-700">Tanggal Mulai</label>
            <input type="date" id="mulai" name="mulai" value="{{ filter.mulai }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <div>
            <label for="akhir" class="block text-sm font-medium text-gray-700">Tanggal Akhir</label>
            <input type="date" id="akhir" name="akhir" value="{{ filter.akhir }}" required
                   class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
        </div>
        <button type="submit" class="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500">
            Terapkan Filter
        </button>
    </form>
    
    <!-- 1. Ringkasan -->
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Ringkasan</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div class="bg-green-50 p-4 rounded-lg border border-green-200">
            <div class="text-sm font-medium text-green-700">Total Pemasukan</div>
            <div class="text-2xl font-bold text-green-900">{{ ringkasan.total_pemasukan | rupiah }}</div>
        </div>
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
                <!-- Rincian Pendapatan -->
                <dt class="text-gray-900 font-semibold">Pendapatan:</dt>
                {% for item in laba_rugi.rincian_pendapatan %}
                <div class="py-2 flex justify-between text-sm ml-4">
                    <dt class="text-gray-600">{{ item.Akun }}</dt>
                    <dd class="text-gray-900 font-medium">{{ item.Jumlah | rupiah }}</dd>
                </div>
                {% else %}
                <div class="py-2 flex justify-between text-sm ml-4">
                    <dt class="text-gray-500">Tidak ada pendapatan</dt>
                    <dd class="text-gray-500 font-medium">Rp 0</dd>
                </div>
                {% endfor %}
                <div class="py-3 flex justify-between text-sm font-semibold border-t border-gray-200">
                    <dt class="text-gray-900">Total Pendapatan</dt>
                    <dd class="text-gray-900">{{ laba_rugi.pendapatan_total | rupiah }}</dd>
                </div>
                
                <!-- Rincian Beban (Kamu bisa tambahkan loop 'beban_df' di sini jika mau) -->
                <div class="py-3 flex justify-between text-sm">
                    <dt class="text-gray-600">Total Pengeluaran (Beban)</dt>
                    <dd class="text-gray-900 font-medium">- {{ laba_rugi.beban_total | rupiah }}</dd>
                </div>
                
                <!-- Total Laba Rugi -->
                <div class="py-3 flex justify-between text-base font-semibold border-t border-gray-300">
                    <dt class="text-gray-900">Laba / Rugi</Kdt>
                    <dd class="{% if laba_rugi.laba_rugi >= 0 %}text-green-700{% else %}text-red-700{% endif %}">
                        {{ laba_rugi.laba_rugi | rupiah }}
                    </dd>
                </div>
            </dl>
        </div>
    </div>
    <!-- Akhir Perubahan Laba Rugi -->

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
                <!-- [PERBAIKAN] Ganti .iterrows() -> loop list biasa -->
                {% for row in jurnal_df %}
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
        {% for akun, data_list in buku_besar.items() %}
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
                        <!-- [PERBAIKAN] Ganti .itertuples() -> loop list biasa -->
                        {% for row in data_list %}
                        <tr>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Tanggal | string | truncate(10, True, '') }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Keterangan | truncate(30, True) }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{{ row.Kontak }}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{% if row.Debit > 0 %}{{ row.Debit | rupiah }}{% endif %}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900">{% if row.Kredit > 0 %}{{ row.Kredit | rupiah }}{% endif %}</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-900 font-medium">{{ row.Saldo | rupiah }}</td>
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


# ---------------- RUTE FLASK (Fokus di sini) ----------------

@app.route("/")
@login_required
def index_page():
    # --- [FIX] Ganti render_template -> render_template_string ---
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_INDEX)
    return render_template_string(full_html, title="Beranda")

# --- [PERBAIKAN V4] INI ADALAH FUNGSI YANG DIPERBAIKI ---
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get('logged_in'):
        return redirect(url_for('index_page'))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip() 
        password = request.form.get("password", "").strip()
        mode = request.form.get("mode")
        
        if not email or not password:
            flash("Email dan password tidak boleh kosong.", "danger")
            return redirect(url_for('login_page'))

        if mode == "Daftar":
            try:
                # Panggil .sign_up
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                })
                
                # 'sign_up' akan raise Exception jika gagal
                
                flash("Akun berhasil dibuat. Cek email-mu untuk verifikasi!", "success")
                
            except Exception as e:
                # Error (misal: "User already registered") akan ditangkap di sini
                flash(f"Gagal mendaftar: {e}", "danger")
            return redirect(url_for('login_page'))
        
        elif mode == "Login":
            try:
                # Panggil .sign_in_with_password
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                session['logged_in'] = True
                
                # [PERBAIKAN V4]
                # Simpan SEMUA data sesi yang kita butuh
                session['username'] = response.user.email 
                session['user_id'] = response.user.id
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                
                flash(f"Login berhasil! Selamat datang, {response.user.email}.", "success")
                return redirect(url_for('index_page'))
            
            except Exception as e:
                flash(f"Gagal login: {e}", "danger")
            return redirect(url_for('login_page'))

    # --- [FIX] Ganti render_template -> render_template_string ---
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LOGIN)
    return render_template_string(full_html, title="Login")

@app.route("/logout")
def logout_page():
    try:
        supabase.auth.sign_out() 
    except Exception as e:
        print(f"Error saat logout Supabase: {e}")
        
    session.clear()
    flash("Anda telah berhasil logout.", "success")
    return redirect(url_for('login_page'))
# --- Akhir Perubahan Auth ---


# --- [PERUBAHAN] Rute Pemasukan ---
@app.route("/pemasukan", methods=["GET", "POST"])
@login_required
def pemasukan_page():
    user_id = session['user_id'] # Ambil user_id dari session
    if request.method == "POST":
        try:
            tanggal = request.form.get("tanggal")
            waktu = datetime.combine(datetime.strptime(tanggal, "%Y-%m-%d").date(), datetime.now().time()).strftime("%Y-%m-%d %H:%M:%S")
            
            sumber = request.form.get("sumber")
            sub_sumber = request.form.get("sub_sumber") 
            
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
            
            data_pemasukan = {
                "Tanggal": waktu, 
                "Sumber": sumber, 
                "Sub_Sumber": sub_sumber, # [Fix] Nama kolom DB pakai underscore
                "Jumlah": jumlah,
                "Metode": metode, 
                "Keterangan": deskripsi, 
                "Kontak": kontak
                # 'user_id' akan ditambahkan oleh 'append_data_to_db'
            }
            # Panggil fungsi DB baru
            append_data_to_db("pemasukan", data_pemasukan, user_id) 
            
            akun_debit = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang", "Pelunasan Piutang": "Kas"}.get(metode, "Kas")
            
            keterangan_jurnal = f"{sumber} - {deskripsi}" 
            if metode == "Pelunasan Piutang":
                akun_kredit = "Piutang Dagang"
                keterangan_jurnal = f"Pelunasan Piutang - {kontak}"
            else:
                akun_kredit = sub_sumber 
            
            # Buat list entri jurnal
            jurnal_entries = [
                {"Tanggal": waktu, "Akun": akun_debit, "Debit": jumlah, "Kredit": 0, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_debit == "Piutang Dagang" else ""},
                {"Tanggal": waktu, "Akun": akun_kredit, "Debit": 0, "Kredit": jumlah, "Keterangan": keterangan_jurnal, "Kontak": ""}
            ]
            # Panggil fungsi DB baru
            buat_jurnal_batch(jurnal_entries, user_id)
                
            flash("Pemasukan berhasil disimpan.", "success")
            return redirect(url_for('pemasukan_page'))
            
        except Exception as e:
            # flash() sudah dipanggil di dalam helper
            return redirect(url_for('pemasukan_page'))
            
    today = datetime.now().strftime("%Y-%m-%d")
    
    # --- [FIX] Ganti render_template -> render_template_string ---
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PEMASUKAN)
    return render_template_string(full_html, title="Pemasukan", kategori_pemasukan=kategori_pemasukan, today=today)
# --- Akhir Perubahan ---


@app.route("/pengeluaran", methods=["GET", "POST"])
@login_required
def pengeluaran_page():
    user_id = session['user_id'] # Ambil user_id dari session
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
            
            data_pengeluaran = {
                "Tanggal": waktu, 
                "Kategori": kategori, 
                "Sub_Kategori": sub_kategori, # [Fix] Nama kolom DB pakai underscore
                "Jumlah": jumlah, 
                "Keterangan": deskripsi, 
                "Metode": metode, 
                "Kontak": kontak
            }
            # Panggil fungsi DB baru
            append_data_to_db("pengeluaran", data_pengeluaran, user_id)
            
            akun_kredit = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang", "Pelunasan Utang": "Kas"}.get(metode, "Kas")
            
            keterangan_jurnal = f"{kategori} - {deskripsi}"
            if metode == "Pelunasan Utang":
                akun_debit = "Utang Dagang"
                keterangan_jurnal = f"Pelunasan Utang - {kontak}"
            else:
                akun_debit = sub_kategori 
            
            # Buat list entri jurnal
            jurnal_entries = [
                {"Tanggal": waktu, "Akun": akun_debit, "Debit": jumlah, "Kredit": 0, "Keterangan": keterangan_jurnal, "Kontak": ""},
                {"Tanggal": waktu, "Akun": akun_kredit, "Debit": 0, "Kredit": jumlah, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_kredit == "Utang Dagang" else ""}
            ]
            # Panggil fungsi DB baru
            buat_jurnal_batch(jurnal_entries, user_id)

            flash("Pengeluaran berhasil disimpan.", "success")
            return redirect(url_for('pengeluaran_page'))

        except Exception as e:
            # flash() sudah dipanggil di dalam helper
            return redirect(url_for('pengeluaran_page'))
            
    today = datetime.now().strftime("%Y-%m-%d")
    
    # --- [FIX] Ganti render_template -> render_template_string ---
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PENGELUARAN)
    return render_template_string(full_html, title="Pengeluaran", kategori_pengeluaran=kategori_pengeluaran, today=today)


@app.route("/kelola")
@login_required
def kelola_page():
    user_id = session['user_id'] # Ambil user_id dari session
    
    # Panggil fungsi DB baru
    pemasukan_df = load_data_from_db("pemasukan", user_id)
    if not pemasukan_df.empty:
        pemasukan_df = pemasukan_df.sort_values(by="Tanggal", ascending=False)
        
    # Panggil fungsi DB baru
    pengeluaran_df = load_data_from_db("pengeluaran", user_id)
    if not pengeluaran_df.empty:
        pengeluaran_df = pengeluaran_df.sort_values(by="Tanggal", ascending=False)
    
    # --- [PERBAIKAN BUG 'id'] ---
    # Ubah DataFrame -> List of Dictionaries
    # Ini FIX untuk error 'dict object has no attribute id'
    pemasukan_list = pemasukan_df.to_dict('records')
    pengeluaran_list = pengeluaran_df.to_dict('records')
    
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_KELOLA_DATA)
    return render_template_string(full_html, title="Kelola Data", 
                                  pemasukan_df=pemasukan_list, pengeluaran_df=pengeluaran_list)

# --- [PERUBAHAN] Rute Hapus ---
@app.route("/hapus/<string:tipe>/<int:db_id>") # Terima db_id, bukan index
@login_required
def hapus_page(tipe, db_id):
    user_id = session['user_id'] # Ambil user_id dari session
    
    if tipe not in ['pemasukan', 'pengeluaran']:
        flash("Tipe transaksi tidak valid.", "danger")
        return redirect(url_for('kelola_page'))
        
    # Panggil fungsi DB baru
    if hapus_transaksi_db(tipe, db_id, user_id):
        flash(f"Data {tipe} ID {db_id} berhasil dihapus dan jurnal pembalikan dibuat.", "success")
    else:
        # Pesan flash error sudah dipanggil di dalam helper
        pass 
        
    return redirect(url_for('kelola_page'))
# --- Akhir Perubahan ---


@app.route("/laporan", methods=["GET", "POST"])
@login_required
def laporan_page():
    user_id = session['user_id'] # Ambil user_id dari session
    
    if request.method == "POST":
        mulai_str = request.form.get("mulai")
        akhir_str = request.form.get("akhir")
    else:
        mulai_str = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        akhir_str = datetime.now().strftime("%Y-%m-%d")
        
    filter_tanggal = {"mulai": mulai_str, "akhir": akhir_str}
    
    try:
        # [PERBAIKAN BUG TANGGAL]
        mulai_dt = pd.to_datetime(mulai_str)
        akhir_dt = pd.to_datetime(akhir_str) + pd.Timedelta(days=1)
    except ValueError:
        flash("Format tanggal tidak valid.", "danger")
        empty_df = pd.DataFrame(columns=["Tanggal", "Akun", "Debit", "Kredit", "Keterangan", "Kontak"])
        # --- [FIX] Ganti render_template -> render_template_string ---
        full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LAPORAN)
        return render_template_string(
            full_html, title="Laporan", filter=filter_tanggal,
            ringkasan={"total_pemasukan": 0, "total_pengeluaran": 0},
            laba_rugi={"rincian_pendapatan": [], "pendapatan_total": 0, "beban_total": 0, "laba_rugi": 0},
            neraca={"aktiva": 0, "kewajiban": 0, "ekuitas": 0},
            buku_pembantu_piutang={}, buku_pembantu_utang={},
            jurnal_df=[], buku_besar={} # [FIX] Kirim list kosong
        )

    # Load data dari DB
    pemasukan_df = load_data_from_db("pemasukan", user_id)
    pengeluaran_df = load_data_from_db("pengeluaran", user_id)
    jurnal_df = load_data_from_db("jurnal", user_id)

    # Konversi kolom Tanggal
    for df in [pemasukan_df, pengeluaran_df, jurnal_df]:
        if not df.empty and "Tanggal" in df.columns:
            # [PERBAIKAN BUG TANGGAL] Ubah jadi datetime, lalu convert ke UTC, lalu hapus info timezone (jadi naive)
            df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors='coerce').dt.tz_convert(None)
            df.dropna(subset=['Tanggal'], inplace=True)
            # [PERBAIKAN] Konversi kolom finansial ke numeric
            for col in ['Jumlah', 'Debit', 'Kredit']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    
    # --- Filter Data (Sekarang aman, naive vs naive) ---
    pemasukan_df_f = pemasukan_df[(pemasukan_df['Tanggal'] >= mulai_dt) & (pemasukan_df['Tanggal'] < akhir_dt)] if not pemasukan_df.empty else pd.DataFrame(columns=pemasukan_df.columns)
    pengeluaran_df_f = pengeluaran_df[(pengeluaran_df['Tanggal'] >= mulai_dt) & (pengeluaran_df['Tanggal'] < akhir_dt)] if not pengeluaran_df.empty else pd.DataFrame(columns=pengeluaran_df.columns)
    jurnal_df_f = jurnal_df[(jurnal_df['Tanggal'] >= mulai_dt) & (jurnal_df['Tanggal'] < akhir_dt)] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    jurnal_total = jurnal_df[jurnal_df['Tanggal'] < akhir_dt] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    # --- Perhitungan ---
    ringkasan = {
        "total_pemasukan": pemasukan_df_f['Jumlah'].sum() if not pemasukan_df_f.empty else 0,
        "total_pengeluaran": pengeluaran_df_f['Jumlah'].sum() if not pengeluaran_df_f.empty else 0
    }

    # --- Perhitungan Laba Rugi BARU ---
    pendapatan_df = pd.DataFrame(columns=['Akun', 'Jumlah'])
    pendapatan_total = 0
    beban_total = 0

    if not jurnal_df_f.empty:
        # 1. Hitung Rincian & Total Pendapatan
        df_pendapatan = jurnal_df_f[
            jurnal_df_f['Akun'].str.startswith("Penjualan -", na=False) | 
            jurnal_df_f['Akun'].str.startswith("Pendapatan -", na=False)
        ]
        if not df_pendapatan.empty:
            pendapatan_df = df_pendapatan.groupby('Akun')['Kredit'].sum().reset_index().rename(columns={'Kredit': 'Jumlah'})
        pendapatan_total = pendapatan_df['Jumlah'].sum()

        # 2. Hitung Total Beban
        beban_akun = []
        for subs in kategori_pengeluaran.values():
            beban_akun.extend(subs)
        beban_total = jurnal_df_f[jurnal_df_f['Akun'].isin(beban_akun)]['Debit'].sum()
        
    laba_rugi_data = {
        "rincian_pendapatan": pendapatan_df.to_dict('records'),
        "pendapatan_total": pendapatan_total,
        "beban_total": beban_total,
        "laba_rugi": pendapatan_total - beban_total
    }
    # --- Akhir Perhitungan Laba Rugi BARU ---


    # --- Perhitungan Neraca BARU ---
    aktiva, kewajiban, ekuitas = 0, 0, 0
    if not jurnal_total.empty:
        aktiva_akun = ['Kas', 'Bank', 'Piutang Dagang']
        kewajiban_akun = ['Utang Dagang']
        
        aktiva = jurnal_total[jurnal_total['Akun'].isin(aktiva_akun)]['Debit'].sum() - \
                 jurnal_total[jurnal_total['Akun'].isin(aktiva_akun)]['Kredit'].sum()
        kewajiban = jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Kredit'].sum() - \
                    jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Debit'].sum()
        
        # Hitung total pendapatan s/d akhir periode
        pendapatan_total_df = jurnal_total[
            jurnal_total['Akun'].str.startswith("Penjualan -", na=False) | 
            jurnal_total['Akun'].str.startswith("Pendapatan -", na=False)
        ]
        pendapatan_total_neraca = 0
        if not pendapatan_total_df.empty:
            pendapatan_total_neraca = pendapatan_total_df['Kredit'].sum()

        # Hitung total beban s/d akhir periode
        beban_akun_total = []
        for subs in kategori_pengeluaran.values():
            beban_akun_total.extend(subs)
        beban_total_neraca = jurnal_total[jurnal_total['Akun'].isin(beban_akun_total)]['Debit'].sum()
        
        ekuitas = pendapatan_total_neraca - beban_total_neraca

    neraca_data = {"aktiva": aktiva, "kewajiban": kewajiban, "ekuitas": ekuitas}
    # --- Akhir Perhitungan Neraca BARU ---

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
            
            # --- [PERBAIKAN BUG 'id'] ---
            # Ubah DataFrame -> List of Dictionaries
            buku_besar_data[akun] = pd.concat([saldo_awal_row, df_akun]).to_dict('records')


    # --- [FIX] Ganti render_template -> render_template_string ---
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
        # [PERBAIKAN BUG 'id']
        jurnal_df=jurnal_df_f.sort_values(by="Tanggal").to_dict('records') if not jurnal_df_f.empty else [],
        buku_besar=buku_besar_data
    )
# --- Akhir Perubahan ---


# ---------------- Menjalankan Aplikasi (LOKAL) ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)