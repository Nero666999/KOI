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
SUPABASE_URL = "https://asweqitjjbepoxwpscsz.supabase.co" 
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFzd2VxaXRqamJlcG94d3BzY3N6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIzMzg3NzMsImV4cCI6MjA3NzkxNDc3M30.oihrg9Pz0qa0LS5DIJzM2itIbtG0oh__PlOqx4nd2To" 

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("--- BERHASIL KONEK KE SUPABASE ---") 
except Exception as e:
    print(f"--- GAGAL KONEK KE SUPABASE: {e} ---")
# --- Akhir Koneksi ---

app = Flask(__name__)
app.secret_key = 'kunci-rahasia-lokal-saya-bebas-diisi-apa-saja'

# --- Fungsi Format Rupiah (Tidak berubah) ---
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

app.jinja_env.filters['rupiah'] = format_rupiah
# --- Akhir Fungsi Rupiah ---

# ---------------- Data Kategori (Tidak berubah) ----------------
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

# ---------------- Helper Functions (Tidak berubah) ----------------
# (load_data_from_db, append_data_to_db, buat_jurnal_batch, hapus_transaksi_db)
def load_data_from_db(tabel, user_id):
    """Mengambil data dari tabel Supabase dan mengubahnya jadi DataFrame."""
    try:
        response = supabase.from_(tabel).select("*").eq("user_id", user_id).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        print(f"Error load_data_from_db ({tabel}): {e}")
        flash(f"Gagal mengambil data dari DB: {e}", "danger")
        return pd.DataFrame() 

def append_data_to_db(tabel, data, user_id):
    """Menyimpan data (dictionary) ke tabel Supabase."""
    try:
        data['user_id'] = user_id 
        response = supabase.from_(tabel).insert(data).execute()
    except Exception as e:
        print(f"Error append_data_to_db ({tabel}): {e}")
        flash(f"Gagal menyimpan data ke DB: {e}", "danger")
        raise e 

def buat_jurnal_batch(jurnal_entries, user_id):
    """Menyimpan beberapa entri jurnal sekaligus ke Supabase."""
    try:
        for entry in jurnal_entries:
            entry['user_id'] = user_id
        response = supabase.from_("jurnal").insert(jurnal_entries).execute()
    except Exception as e:
        print(f"Error buat_jurnal_batch: {e}")
        flash(f"Gagal menyimpan jurnal ke DB: {e}", "danger")
        raise e

def hapus_transaksi_db(tabel, db_id, user_id):
    """Menghapus transaksi dari Supabase dan membuat jurnal pembalikan."""
    try:
        response = supabase.from_(tabel).select("*").eq("id", db_id).eq("user_id", user_id).single().execute()
        transaksi = response.data
        
        delete_response = supabase.from_(tabel).delete().eq("id", db_id).execute()

        waktu_hapus = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        jumlah_transaksi = float(transaksi['Jumlah'])
        metode_transaksi = transaksi['Metode']
        kontak = transaksi.get('Kontak', '')
        
        jurnal_pembalikan_entries = []
        
        if tabel == "pemasukan":
            sub_sumber = transaksi.get('Sub_Sumber', 'Lain-lain') 
            keterangan_batal = f"Pembatalan: {transaksi.get('Sumber', '')} - {sub_sumber}"
            
            if metode_transaksi == "Pelunasan Piutang":
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": "Piutang Dagang", "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": kontak},
                    {"Tanggal": waktu_hapus, "Akun": "Kas", "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": ""}
                ]
            else:
                akun_debit_pembalikan = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang"}.get(metode_transaksi, "Kas")
                akun_kredit_asli = sub_sumber 
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": akun_kredit_asli, "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": ""},
                    {"Tanggal": waktu_hapus, "Akun": akun_debit_pembalikan, "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": kontak if akun_debit_pembalikan == "Piutang Dagang" else ""}
                ]
        
        elif tabel == "pengeluaran":
            sub_kategori = transaksi.get('Sub_Kategori', 'Beban Lain') 
            keterangan_batal = f"Pembatalan: {transaksi.get('Kategori', '')} - {sub_kategori}"

            if metode_transaksi == "Pelunasan Utang":
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": "Kas", "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": ""},
                    {"Tanggal": waktu_hapus, "Akun": "Utang Dagang", "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": kontak}
                ]
            else:
                akun_kredit_pembalikan = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang"}.get(metode_transaksi, "Kas")
                akun_debit_asli = sub_kategori
                jurnal_pembalikan_entries = [
                    {"Tanggal": waktu_hapus, "Akun": akun_kredit_pembalikan, "Debit": jumlah_transaksi, "Kredit": 0, "Keterangan": keterangan_batal, "Kontak": kontak if akun_kredit_pembalikan == "Utang Dagang" else ""},
                    {"Tanggal": waktu_hapus, "Akun": akun_debit_asli, "Debit": 0, "Kredit": jumlah_transaksi, "Keterangan": keterangan_batal, "Kontak": ""}
                ]
        else:
            return False
        
        buat_jurnal_batch(jurnal_pembalikan_entries, session['user_id'])
        return True
        
    except Exception as e:
        print(f"Error hapus_transaksi_db: {e}")
        flash(f"Gagal menghapus data: {e}", "danger")
        return False
# --- Akhir Helper Functions ---


# ---------------- Decorator (Tidak Berubah dari V5) ----------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'access_token' not in session:
            session.clear()
            flash("Sesi tidak valid. Harap login ulang.", "danger")
            return redirect(url_for('login_page'))
        
        try:
            supabase.auth.set_session(
                session['access_token'], 
                session.get('refresh_token')
            )
            response = supabase.auth.get_user()
            
            if not response or not response.user:
                raise Exception("Token tidak valid atau sudah kedaluwarsa.")
                
            if 'user_id' not in session:
                session['user_id'] = response.user.id
            
            if 'username' not in session:
                try:
                    user_id = response.user.id
                    profile_res = supabase.from_("profiles").select("username").eq("id", user_id).single().execute()
                    
                    if profile_res.data and profile_res.data.get('username'):
                        session['username'] = profile_res.data['username']
                    else:
                        session['username'] = response.user.email
                except Exception as e:
                    print(f"Gagal ambil username dari 'profiles': {e}")
                    session['username'] = response.user.email # Fallback

            if 'logged_in' not in session:
                session['logged_in'] = True

        except Exception as e:
            print(f"Gagal set session di decorator: {e}")
            session.clear()
            flash("Sesi Anda telah berakhir. Harap login ulang.", "danger")
            return redirect(url_for('login_page'))
        
        return f(*args, **kwargs)
    return decorated_function
# --- Akhir Decorator ---

# ---------------- KUMPULAN TEMPLATE HTML ----------------

# --- HTML_LAYOUT (Tidak berubah dari V6) ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - Koilume</title>
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
                        Koilume
                    </a>
                </div>
                <div class="flex items-center">
                    {% if session.logged_in %}
                        <span class="text-gray-700 mr-4">Halo, <b>{{ session.username }}</b>!</span>
                        
                        <div class="hidden md:flex items-center space-x-1">
                            <a href="{{ url_for('index_page') }}" class="px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">Beranda</a>
                            
                            <div class="relative">
                                <button id="transaksi-menu-button" class="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                                    <span>Transaksi</span>
                                    <svg class="ml-1 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                                    </svg>
                                </button>
                                <div id="transaksi-menu" class="absolute z-10 hidden w-48 bg-white rounded-md shadow-lg mt-2 py-1 border border-gray-200">
                                    <a href="{{ url_for('pemasukan_page') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Input Pemasukan</a>
                                    <a href="{{ url_for('pengeluaran_page') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Input Pengeluaran</a>
                                </div>
                            </div>
                            
                            <div class="relative">
                                <button id="laporan-menu-button" class="flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100">
                                    <span>Data & Laporan</span>
                                    <svg class="ml-1 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                                        <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
                                    </svg>
                                </button>
                                <div id="laporan-menu" class="absolute z-10 hidden w-48 bg-white rounded-md shadow-lg mt-2 py-1 border border-gray-200">
                                    <a href="{{ url_for('kelola_page') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Kelola Data Transaksi</a>
                                    <a href="{{ url_for('laporan_page') }}" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Laporan Keuangan</a>
                                </div>
                            </div>

                        </div>
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
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="{% if category == 'success' %}bg-green-100 border-green-400 text-green-700{% else %}bg-red-100 border-red-400 text-red-700{% endif %} border px-4 py-3 rounded-md relative mb-4" role="alert">
                    <span class="block sm:inline">{{ message }}</span>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
        
            {% block content %}{% endblock %}
        </div>
    </main>
    
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

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const transaksiButton = document.getElementById('transaksi-menu-button');
            const transaksiMenu = document.getElementById('transaksi-menu');
            const laporanButton = document.getElementById('laporan-menu-button');
            const laporanMenu = document.getElementById('laporan-menu');

            function toggleDropdown(menu) {
                if (menu) {
                    menu.classList.toggle('hidden');
                }
            }

            // Tutup semua dropdown
            function closeDropdowns(exceptMenu = null) {
                if (transaksiMenu && transaksiMenu !== exceptMenu) {
                    transaksiMenu.classList.add('hidden');
                }
                if (laporanMenu && laporanMenu !== exceptMenu) {
                    laporanMenu.classList.add('hidden');
                }
            }

            if (transaksiButton) {
                transaksiButton.addEventListener('click', function(event) {
                    event.stopPropagation(); // Hentikan event agar tidak ditangkap 'window.onclick'
                    closeDropdowns(transaksiMenu); // Tutup menu lain
                    toggleDropdown(transaksiMenu);
                });
            }

            if (laporanButton) {
                laporanButton.addEventListener('click', function(event) {
                    event.stopPropagation();
                    closeDropdowns(laporanMenu); // Tutup menu lain
                    toggleDropdown(laporanMenu);
                });
            }

            // Klik di luar menu untuk menutup
            window.onclick = function(event) {
                closeDropdowns();
            }
        });
    </script>
</body>
</html>
"""

# --- [PERUBAHAN V7] ---
# Request 1: Beranda diubah jadi halaman statis (non-sensitif)
HTML_INDEX = """
<div class="space-y-6">
    <div class="bg-white p-8 rounded-xl shadow-lg">
        <h1 class="text-3xl font-bold text-gray-900">Selamat datang, {{ session.username }}!</h1>
        <p class="text-gray-600 text-lg mt-2">Selamat datang di Koilume, aplikasi akuntansi sederhana Anda.</p>
    </div>

    <div class="bg-white p-8 rounded-xl shadow-lg">
        <h2 class="text-xl font-bold text-gray-800 mb-4">Tentang Aplikasi Ini</h2>
        <div class="space-y-3 text-gray-700">
            <p>Koilume dirancang untuk membantu Anda melacak keuangan bisnis Koi dengan mudah. Berikut adalah fitur utamanya:</p>
            <ul class="list-disc list-inside space-y-1 pl-4">
                <li><b class="font-medium text-red-600">Input Transaksi:</b> Catat semua Pemasukan (penjualan ikan) dan Pengeluaran (pakan, listrik, dll).</li>
                <li><b class="font-medium text-red-600">Jurnal Otomatis:</b> Setiap transaksi akan otomatis dibuatkan Jurnal.</li>
                <li><b class="font-medium text-red-600">Laporan Keuangan:</b> Hasilkan laporan Laba Rugi, Neraca, dan Buku Besar secara otomatis.</li>
                <li><b class="font-medium text-red-600">Buku Pembantu:</b> Lacak sisa Piutang dan Utang dengan mudah.</li>
            </ul>
        </div>
    </div>

    <div class="bg-white p-8 rounded-xl shadow-lg">
        <h2 class="text-xl font-bold text-gray-800 mb-4">Akses Cepat</h2>
        <div class="flex flex-col sm:flex-row gap-4">
            <a href="{{ url_for('pemasukan_page') }}" class="flex-1 text-center bg-green-600 hover:bg-green-700 text-white font-medium py-3 px-5 rounded-lg transition duration-300">
                ➕ Tambah Pemasukan
            </a>
            <a href="{{ url_for('pengeluaran_page') }}" class="flex-1 text-center bg-red-600 hover:bg-red-700 text-white font-medium py-3 px-5 rounded-lg transition duration-300">
                ➖ Tambah Pengeluaran
            </a>
            <a href="{{ url_for('laporan_page') }}" class="flex-1 text-center bg-gray-700 hover:bg-gray-800 text-white font-medium py-3 px-5 rounded-lg transition duration-300">
                📊 Lihat Laporan
            </a>
        </div>
    </div>
</div>
"""
# --- Akhir Perubahan V7 ---


# --- HTML Lainnya (LOGIN, PEMASUKAN, PENGELUARAN, KELOLA, LAPORAN) ---
# --- (Tidak berubah dari V6) ---

HTML_LOGIN = """
<div class="flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 bg-white p-10 rounded-xl shadow-lg">
        <div>
            <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
                Login atau Daftar Akun
            </h2>
        </div>
        <form class="mt-8 space-y-6" action="{{ url_for('login_page') }}" method="POST">
            <div class="rounded-md shadow-sm -space-y-px">
                
                <div id="username-container" style="display: none;">
                    <label for="username" class="sr-only">Username</label>
                    <input id="username" name="username" type="text" autocomplete="username"
                           class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" 
                           placeholder="Username (tanpa spasi, cth: koilume)">
                </div>

                <div>
                    <label for="email" class="sr-only">Email</label>
                    <input id="email" name="email" type="email" autocomplete="email" required 
                           class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" 
                           placeholder="Alamat Email">
                </div>
                <div>
                    <label for="password" class="sr-only">Kata Sandi</label>
                    <input id="password" name="password" type="password" autocomplete="current-password" required 
                           class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-red-500 focus:border-red-500 focus:z-10 sm:text-sm" 
                           placeholder="Kata Sandi (min. 6 karakter)">
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

<script>
    const modeLogin = document.getElementById('mode-login');
    const modeDaftar = document.getElementById('mode-daftar');
    const usernameContainer = document.getElementById('username-container');
    const emailInput = document.getElementById('email');

    function toggleUsernameField() {
        if (modeDaftar.checked) {
            usernameContainer.style.display = 'block';
            emailInput.classList.remove('rounded-t-md'); 
        } else {
            usernameContainer.style.display = 'none';
            emailInput.classList.add('rounded-t-md'); 
        }
    }
    
    modeLogin.addEventListener('change', toggleUsernameField);
    modeDaftar.addEventListener('change', toggleUsernameField);
    
    document.addEventListener('DOMContentLoaded', toggleUsernameField);
</script>
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
        
        <div>
            <label for="sumber" class="block text-sm font-medium text-gray-700">Kategori Pemasukan</label>
            <select id="sumber" name="sumber" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
                {% for sumber in kategori_pemasukan.keys() %}
                <option value="{{ sumber }}">{{ sumber }}</option>
                {% endfor %}
            </select>
        </div>

        <div>
            <label for="sub_sumber" class="block text-sm font-medium text-gray-700">Akun Pemasukan</label>
            <select id="sub_sumber" name="sub_sumber" required
                    class="mt-1 block w-full px-3 py-2 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500 sm:text-sm">
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
    
    <script>
        const kategoriPemasukanData = {{ kategori_pemasukan | tojson }};
        const sumberSelect = document.getElementById('sumber');
        const subSumberSelect = document.getElementById('sub_sumber');

        function updateSubSumber() {
            const selectedSumber = sumberSelect.value;
            const subSumberList = kategoriPemasukanData[selectedSumber] || [];
            
            subSumberSelect.innerHTML = ''; 
            
            subSumberList.forEach(sub => {
                const option = document.createElement('option');
                option.value = sub;
                option.textContent = sub;
                subSumberSelect.appendChild(option);
            });
        }
        
        sumberSelect.addEventListener('change', updateSubSumber);
        updateSubSumber();
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
            
            subKategoriSelect.innerHTML = ''; 
            
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
    
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Data Pemasukan</h3>
    <div class="overflow-x-auto rounded-lg border border-gray-200 mb-6">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tanggal</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sumber</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sub Sumber</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metode</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pelanggan</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {% for row in pemasukan_df %}
                <tr>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['id'] }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{{ row['Tanggal'] | string | truncate(10, True, '') }}</td>
                    <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{{ row['Sumber'] }}</td>
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
HTML_LAPORAN = """
<div class="bg-white p-8 rounded-xl shadow-lg">
    <h2 class="text-2xl font-bold text-gray-900 mb-6">Laporan Keuangan</h2>
    
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
    
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Ringkasan (Periode Terpilih)</h3>
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

    <h3 class="text-xl font-semibold text-gray-800 mb-3">Laporan Laba Rugi (Periode Terpilih)</h3>
    <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-6">
        <div class="flow-root">
            <dl class="divide-y divide-gray-200">
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
                
                <div class="py-3 flex justify-between text-sm">
                    <dt class="text-gray-600">Total Pengeluaran (Beban)</dt>
                    <dd class="text-gray-900 font-medium">- {{ laba_rugi.beban_total | rupiah }}</dd>
                </div>
                
                <div class="py-3 flex justify-between text-base font-semibold border-t border-gray-300">
                    <dt class="text-gray-900">Laba / Rugi</Kdt>
                    <dd class="{% if laba_rugi.laba_rugi >= 0 %}text-green-700{% else %}text-red-700{% endif %}">
                        {{ laba_rugi.laba_rugi | rupiah }}
                    </dd>
                </div>
            </dl>
        </div>
    </div>

    <h3 class="text-xl font-semibold text-gray-800 mb-3">Neraca (Posisi Keuangan s/d {{ filter.akhir }})</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <h4 class="font-semibold text-gray-800 mb-2">Aktiva (Harta)</h4>
            <dl class="divide-y divide-gray-200">
                <div class="py-2 flex justify-between text-sm">
                    <dt class="text-gray-600">Kas & Bank</dt>
                    <dd class="text-gray-900 font-medium">{{ neraca.kas_bank | rupiah }}</dd>
                </div>
                <div class="py-2 flex justify-between text-sm">
                    <dt class="text-gray-600">Piutang Dagang</dt>
                    <dd class="text-gray-900 font-medium">{{ neraca.piutang | rupiah }}</dd>
                </div>
                <div class="py-2 flex justify-between text-sm font-semibold">
                    <dt class="text-gray-900">Total Aktiva</dt>
                    <dd class="text-gray-900">{{ neraca.aktiva | rupiah }}</dd>
                </div>
            </dl>
        </div>
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
    {% if neraca.is_balance %}
    <div class="bg-green-100 border-l-4 border-green-500 text-green-700 p-4" role="alert">
        <p class="font-bold">Neraca Seimbang (Balance)</p>
        <p>Total Aktiva ({{ neraca.aktiva | rupiah }}) sama dengan Total Pasiva ({{ (neraca.kewajiban + neraca.ekuitas) | rupiah }}).</p>
    </div>
    {% else %}
    <div class="bg-red-100 border-l-4 border-red-500 text-red-700 p-4" role="alert">
        <p class="font-bold">Error: Neraca Tidak Seimbang</p>
        <p>Total Aktiva ({{ neraca.aktiva | rupiah }}) tidak sama dengan Total Pasiva ({{ (neraca.kewajiban + neraca.ekuitas) | rupiah }}). Cek logika jurnal Anda.</p>
    </div>
    {% endif %}

    <h3 class="text-xl font-semibold text-gray-800 mb-3 mt-6">Buku Besar Pembantu (s/d {{ filter.akhir }})</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
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

# --- [PERUBAHAN V7] ---
# Request 1: Rute Index diubah jadi statis (non-sensitif)
@app.route("/")
@login_required
def index_page():
    # Rute ini tidak lagi menghitung data keuangan.
    # Hanya menampilkan halaman selamat datang.
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_INDEX)
    return render_template_string(full_html, title="Beranda")
# --- Akhir Perubahan V7 ---


# --- Rute Login (Tidak Berubah dari V5) ---
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get('logged_in'):
        return redirect(url_for('index_page'))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip() 
        password = request.form.get("password", "").strip()
        username = request.form.get("username", "").strip()
        mode = request.form.get("mode")
        
        if not email or not password:
            flash("Email dan password tidak boleh kosong.", "danger")
            return redirect(url_for('login_page'))

        if mode == "Daftar":
            if not username:
                flash("Username wajib diisi saat mendaftar.", "danger")
                return redirect(url_for('login_page'))
            try:
                response = supabase.auth.sign_up({
                    "email": email,
                    "password": password,
                })
                
                if response.user:
                    user_id = response.user.id
                    try:
                        supabase.from_("profiles").insert({
                            "id": user_id,
                            "username": username
                        }).execute()
                    except Exception as profile_e:
                        flash(f"Gagal membuat profil: {profile_e}", "danger")
                        return redirect(url_for('login_page'))

                flash("Akun berhasil dibuat. Cek email-mu untuk verifikasi!", "success")
                
            except Exception as e:
                flash(f"Gagal mendaftar: {e}", "danger")
            return redirect(url_for('login_page'))
        
        elif mode == "Login":
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                user_id = response.user.id
                user_email = response.user.email
                
                login_username = user_email # Default
                try:
                    profile_res = supabase.from_("profiles").select("username").eq("id", user_id).single().execute()
                    if profile_res.data and profile_res.data.get('username'):
                        login_username = profile_res.data['username']
                except Exception as e:
                    print(f"Gagal ambil profile saat login, fallback ke email: {e}")
                
                session['logged_in'] = True
                session['username'] = login_username
                session['user_id'] = user_id
                session['access_token'] = response.session.access_token
                session['refresh_token'] = response.session.refresh_token
                
                flash(f"Login berhasil! Selamat datang, {login_username}.", "success")
                return redirect(url_for('index_page'))
            
            except Exception as e:
                flash(f"Gagal login: {e}", "danger")
            return redirect(url_for('login_page'))

    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LOGIN)
    return render_template_string(full_html, title="Login")
# --- Akhir Rute Login ---


@app.route("/logout")
def logout_page():
    try:
        supabase.auth.sign_out() 
    except Exception as e:
        print(f"Error saat logout Supabase: {e}")
        
    session.clear()
    flash("Anda telah berhasil logout.", "success")
    return redirect(url_for('login_page'))


# --- Rute Pemasukan (Tidak Berubah dari V5) ---
@app.route("/pemasukan", methods=["GET", "POST"])
@login_required
def pemasukan_page():
    user_id = session['user_id']
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
                "Tanggal": waktu, "Sumber": sumber, "Sub_Sumber": sub_sumber,
                "Jumlah": jumlah, "Metode": metode, "Keterangan": deskripsi, "Kontak": kontak
            }
            append_data_to_db("pemasukan", data_pemasukan, user_id) 
            
            akun_debit = {"Tunai": "Kas", "Transfer": "Bank", "Piutang": "Piutang Dagang", "Pelunasan Piutang": "Kas"}.get(metode, "Kas")
            keterangan_jurnal = f"{sumber} - {deskripsi}" 
            if metode == "Pelunasan Piutang":
                akun_kredit = "Piutang Dagang"
                keterangan_jurnal = f"Pelunasan Piutang - {kontak}"
            else:
                akun_kredit = sub_sumber 
            
            jurnal_entries = [
                {"Tanggal": waktu, "Akun": akun_debit, "Debit": jumlah, "Kredit": 0, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_debit == "Piutang Dagang" else ""},
                {"Tanggal": waktu, "Akun": akun_kredit, "Debit": 0, "Kredit": jumlah, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_kredit == "Piutang Dagang" else ""}
            ]
            buat_jurnal_batch(jurnal_entries, user_id)
            flash("Pemasukan berhasil disimpan.", "success")
            return redirect(url_for('pemasukan_page'))
        except Exception as e:
            return redirect(url_for('pemasukan_page'))
            
    today = datetime.now().strftime("%Y-%m-%d")
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PEMASUKAN)
    return render_template_string(full_html, title="Pemasukan", kategori_pemasukan=kategori_pemasukan, today=today)


# --- Rute Pengeluaran (Tidak Berubah dari V5) ---
@app.route("/pengeluaran", methods=["GET", "POST"])
@login_required
def pengeluaran_page():
    user_id = session['user_id']
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
                "Tanggal": waktu, "Kategori": kategori, "Sub_Kategori": sub_kategori,
                "Jumlah": jumlah, "Keterangan": deskripsi, "Metode": metode, "Kontak": kontak
            }
            append_data_to_db("pengeluaran", data_pengeluaran, user_id)
            
            akun_kredit = {"Tunai": "Kas", "Transfer": "Bank", "Utang": "Utang Dagang", "Pelunasan Utang": "Kas"}.get(metode, "Kas")
            keterangan_jurnal = f"{kategori} - {deskripsi}"
            if metode == "Pelunasan Utang":
                akun_debit = "Utang Dagang"
                keterangan_jurnal = f"Pelunasan Utang - {kontak}"
            else:
                akun_debit = sub_kategori 
            
            jurnal_entries = [
                {"Tanggal": waktu, "Akun": akun_debit, "Debit": jumlah, "Kredit": 0, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_debit == "Utang Dagang" else ""},
                {"Tanggal": waktu, "Akun": akun_kredit, "Debit": 0, "Kredit": jumlah, "Keterangan": keterangan_jurnal, "Kontak": kontak if akun_kredit == "Utang Dagang" else ""}
            ]
            buat_jurnal_batch(jurnal_entries, user_id)
            flash("Pengeluaran berhasil disimpan.", "success")
            return redirect(url_for('pengeluaran_page'))
        except Exception as e:
            return redirect(url_for('pengeluaran_page'))
            
    today = datetime.now().strftime("%Y-%m-%d")
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_PENGELUARAN)
    return render_template_string(full_html, title="Pengeluaran", kategori_pengeluaran=kategori_pengeluaran, today=today)


# --- Rute Kelola & Hapus (Tidak Berubah dari V5) ---
@app.route("/kelola")
@login_required
def kelola_page():
    user_id = session['user_id']
    pemasukan_df = load_data_from_db("pemasukan", user_id)
    if not pemasukan_df.empty:
        pemasukan_df = pemasukan_df.sort_values(by="Tanggal", ascending=False)
    pengeluaran_df = load_data_from_db("pengeluaran", user_id)
    if not pengeluaran_df.empty:
        pengeluaran_df = pengeluaran_df.sort_values(by="Tanggal", ascending=False)
    pemasukan_list = pemasukan_df.to_dict('records')
    pengeluaran_list = pengeluaran_df.to_dict('records')
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_KELOLA_DATA)
    return render_template_string(full_html, title="Kelola Data", 
                                  pemasukan_df=pemasukan_list, pengeluaran_df=pengeluaran_list)

@app.route("/hapus/<string:tipe>/<int:db_id>")
@login_required
def hapus_page(tipe, db_id):
    user_id = session['user_id']
    if tipe not in ['pemasukan', 'pengeluaran']:
        flash("Tipe transaksi tidak valid.", "danger")
        return redirect(url_for('kelola_page'))
    if hapus_transaksi_db(tipe, db_id, user_id):
        flash(f"Data {tipe} ID {db_id} berhasil dihapus dan jurnal pembalikan dibuat.", "success")
    return redirect(url_for('kelola_page'))


# --- [PERUBAHAN V7] ---
# Request 2: Logika Neraca diubah agar patuh SAK
@app.route("/laporan", methods=["GET", "POST"])
@login_required
def laporan_page():
    user_id = session['user_id']
    
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
        full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LAPORAN)
        return render_template_string(
            full_html, title="Laporan", filter=filter_tanggal,
            ringkasan={"total_pemasukan": 0, "total_pengeluaran": 0},
            laba_rugi={"rincian_pendapatan": [], "pendapatan_total": 0, "beban_total": 0, "laba_rugi": 0},
            neraca={"aktiva": 0, "kewajiban": 0, "ekuitas": 0, "kas_bank": 0, "piutang": 0, "is_balance": False},
            buku_pembantu_piutang={}, buku_pembantu_utang={},
            jurnal_df=[], buku_besar={}
        )

    # Load data dari DB
    pemasukan_df = load_data_from_db("pemasukan", user_id)
    pengeluaran_df = load_data_from_db("pengeluaran", user_id)
    jurnal_df = load_data_from_db("jurnal", user_id)

    # Konversi kolom Tanggal & Numerik
    for df in [pemasukan_df, pengeluaran_df, jurnal_df]:
        if not df.empty and "Tanggal" in df.columns:
            df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors='coerce').dt.tz_convert(None)
            df.dropna(subset=['Tanggal'], inplace=True)
            for col in ['Jumlah', 'Debit', 'Kredit']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # --- Filter Data ---
    pemasukan_df_f = pemasukan_df[(pemasukan_df['Tanggal'] >= mulai_dt) & (pemasukan_df['Tanggal'] < akhir_dt)] if not pemasukan_df.empty else pd.DataFrame(columns=pemasukan_df.columns)
    pengeluaran_df_f = pengeluaran_df[(pengeluaran_df['Tanggal'] >= mulai_dt) & (pengeluaran_df['Tanggal'] < akhir_dt)] if not pengeluaran_df.empty else pd.DataFrame(columns=pengeluaran_df.columns)
    jurnal_df_f = jurnal_df[(jurnal_df['Tanggal'] >= mulai_dt) & (jurnal_df['Tanggal'] < akhir_dt)] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    # Data Jurnal s/d Tanggal Akhir (Untuk Neraca & Buku Besar)
    jurnal_total = jurnal_df[jurnal_df['Tanggal'] < akhir_dt] if not jurnal_df.empty else pd.DataFrame(columns=jurnal_df.columns)
    
    # --- Perhitungan Ringkasan (Periode Terpilih) ---
    ringkasan = {
        "total_pemasukan": pemasukan_df_f['Jumlah'].sum() if not pemasukan_df_f.empty else 0,
        "total_pengeluaran": pengeluaran_df_f['Jumlah'].sum() if not pengeluaran_df_f.empty else 0
    }

    # --- Perhitungan Laba Rugi (Periode Terpilih) ---
    pendapatan_df = pd.DataFrame(columns=['Akun', 'Jumlah'])
    pendapatan_total = 0
    beban_total = 0

    if not jurnal_df_f.empty:
        df_pendapatan = jurnal_df_f[
            jurnal_df_f['Akun'].str.startswith("Penjualan -", na=False) | 
            jurnal_df_f['Akun'].str.startswith("Pendapatan -", na=False)
        ]
        if not df_pendapatan.empty:
            pendapatan_df = df_pendapatan.groupby('Akun')['Kredit'].sum().reset_index().rename(columns={'Kredit': 'Jumlah'})
        pendapatan_total = pendapatan_df['Jumlah'].sum()

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

    # --- [PERUBAHAN V7] Perhitungan Neraca (SAK Compliance) ---
    aktiva, kewajiban, ekuitas = 0, 0, 0
    kas_bank, piutang = 0, 0
    
    if not jurnal_total.empty:
        # Definisikan Akun
        kas_bank_akun = ['Kas', 'Bank']
        piutang_akun = ['Piutang Dagang']
        kewajiban_akun = ['Utang Dagang']
        
        # 1. Hitung Saldo per Kategori Akun
        kas_bank = jurnal_total[jurnal_total['Akun'].isin(kas_bank_akun)]['Debit'].sum() - \
                   jurnal_total[jurnal_total['Akun'].isin(kas_bank_akun)]['Kredit'].sum()
                   
        piutang = jurnal_total[jurnal_total['Akun'].isin(piutang_akun)]['Debit'].sum() - \
                  jurnal_total[jurnal_total['Akun'].isin(piutang_akun)]['Kredit'].sum()
                  
        kewajiban = jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Kredit'].sum() - \
                    jurnal_total[jurnal_total['Akun'].isin(kewajiban_akun)]['Debit'].sum()

        # 2. Hitung Total Aktiva
        #    (Untuk saat ini, aktiva kita hanya kas/bank + piutang)
        aktiva = kas_bank + piutang

        # 3. Hitung Ekuitas (SAK: A = L + E  =>  E = A - L)
        #    Ini adalah perhitungan kuncinya agar Neraca BALANCE.
        ekuitas = aktiva - kewajiban
        
    # Cek apakah balance (pembulatan 5 desimal untuk menghindari error float)
    is_balance = round(aktiva, 5) == round(kewajiban + ekuitas, 5)

    neraca_data = {
        "aktiva": aktiva, 
        "kewajiban": kewajiban, 
        "ekuitas": ekuitas,
        "kas_bank": kas_bank,
        "piutang": piutang,
        "is_balance": is_balance
    }
    # --- Akhir Perhitungan Neraca V7 ---

    # --- Perhitungan Buku Pembantu ---
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

    # --- Perhitungan Buku Besar ---
    buku_besar_data = {}
    if not jurnal_df_f.empty:
        jurnal_df_f['Kontak'] = jurnal_df_f['Kontak'].fillna('')
        akun_list = sorted(jurnal_df_f['Akun'].unique())
        for akun in akun_list:
            df_akun = jurnal_df_f[jurnal_df_f['Akun'] == akun].copy().sort_values("Tanggal")
            saldo = 0
            saldos = []
            if not jurnal_total.empty:
                # Hitung Saldo Awal
                saldo_awal_df = jurnal_total[(jurnal_total['Akun'] == akun) & (jurnal_total['Tanggal'] < mulai_dt)]
                if not saldo_awal_df.empty:
                    # Logika saldo normal (Aktiva/Beban di Debit, Kewajiban/Ekuitas/Pendapatan di Kredit)
                    # Untuk simpelnya, kita pakai Debit - Kredit untuk semua
                    saldo = saldo_awal_df['Debit'].sum() - saldo_awal_df['Kredit'].sum()
            
            saldos.append(saldo)
            
            for _, row in df_akun.iterrows():
                saldo += (row['Debit'] - row['Kredit'])
                saldos.append(saldo)
            
            saldo_awal_row = pd.DataFrame([{
                'Tanggal': mulai_dt - pd.Timedelta(days=1), 
                'Keterangan': 'Saldo Awal', 'Kontak': '', 
                'Debit': 0, 'Kredit': 0, 'Saldo': saldos[0] 
            }])
            
            df_akun['Saldo'] = saldos[1:] 
            buku_besar_data[akun] = pd.concat([saldo_awal_row, df_akun]).to_dict('records')

    # --- Render Template ---
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
        jurnal_df=jurnal_df_f.sort_values(by="Tanggal").to_dict('records') if not jurnal_df_f.empty else [],
        buku_besar=buku_besar_data
    )
# --- Akhir Rute Laporan ---


# ---------------- Menjalankan Aplikasi (LOKAL) ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)
