# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
try:
    from flask_mail import Mail, Message
    mail_available = True
except ImportError:
    mail_available = False
    print("Flask-Mail nincs telepítve. E-mail funkciók nem elérhetők.")
    print("Telepítés: pip install flask-mail")
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    psycopg2_available = True
except ImportError:
    psycopg2_available = False
    print("psycopg2 nincs telepítve. PostgreSQL funkciók nem elérhetők.")
    print("Telepítés: pip install psycopg2-binary")
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
import json
import os
import pandas as pd

# Flask alkalmazás inicializálása
app = Flask(__name__)
app.secret_key = 'titkos_kulcs_123'  # Éles környezetben cseréld ki biztonságosra!

# Feltöltési mappa konfigurációja
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Feltöltési mappa létrehozása ha nem létezik
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# E-mail konfiguráció (Gmail példa)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Cseréld ki a saját email címedre
app.config['MAIL_PASSWORD'] = 'your_app_password'     # App jelszó szükséges Gmail esetén
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'

if mail_available:
    mail = Mail(app)
else:
    mail = None

# PostgreSQL adatbázis konfiguráció
DB_CONFIG = {
    'host': 'localhost',
    'user': 'postgres',          # Cseréld ki a saját PostgreSQL felhasználónevedre
    'password': 'password',      # Cseréld ki a saját PostgreSQL jelszavadra
    'database': 'webaruház',
    'port': 5432
}


import psycopg2

def allowed_file(filename):
    """Ellenőrzi, hogy a fájl kiterjesztése engedélyezett-e"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection(dbname="webaruhaz"):
    try:
        connection = psycopg2.connect(
            dbname=dbname,
            user="tomasovszkiadrian",
            password="",  # jelszó, ha kell
            host="localhost",
            port=5432
        )
        return connection
    except Exception as e:
        print("Adatbázis kapcsolódási hiba:", e)
        return None

def init_database():
    try:
        connection = get_db_connection()  # alap adatbázishoz, pl. 'postgres'
        connection.autocommit = True
        cursor = connection.cursor()

        try:
            cursor.execute("CREATE DATABASE webaruhaz")
            print("1 tábla OK")
        except Exception as e:
            print("Adatbázis létrehozása közben hiba vagy már létezik:", e)

        cursor.close()
        connection.close()

        connection = get_db_connection(dbname="webaruhaz")
        cursor = connection.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS felhasznalok (
                id SERIAL PRIMARY KEY,
                email VARCHAR(100) UNIQUE NOT NULL,
                jelszo VARCHAR(255) NOT NULL,
                nev VARCHAR(100) NOT NULL,
                szerepkor VARCHAR(10) DEFAULT 'user' CHECK (szerepkor IN ('user', 'admin')),
                letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("2 tábla OK")
        
        # Kategóriák tábla létrehozása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kategoriak (
                id SERIAL PRIMARY KEY,
                nev VARCHAR(100) NOT NULL,
                leiras TEXT
            )
        ''')
        print("3 tábla OK")
        
        # Termékek tábla létrehozása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS termekek (
                id SERIAL PRIMARY KEY,
                nev VARCHAR(200) NOT NULL,
                leiras TEXT,
                ar DECIMAL(10,2) NOT NULL,
                kategoria_id INT,
                kep_url VARCHAR(500),
                aktiv BOOLEAN DEFAULT TRUE,
                letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (kategoria_id) REFERENCES kategoriak(id)
            )
        ''')
        print("4 tábla OK")
        
        # Rendelések tábla létrehozása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rendelesek (
                id SERIAL PRIMARY KEY,
                felhasznalo_id INT NOT NULL,
                osszeg DECIMAL(10,2) NOT NULL,
                statusz VARCHAR(20) DEFAULT 'feldolgozás alatt' CHECK (statusz IN ('feldolgozás alatt', 'teljesítve', 'törölve')),
                rendeles_datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (felhasznalo_id) REFERENCES felhasznalok(id)
            )
        ''')
        print("5 tábla OK")
        
        # Rendelés tételek tábla létrehozása
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rendeles_tetelek (
                id SERIAL PRIMARY KEY,
                rendeles_id INT NOT NULL,
                termek_id INT NOT NULL,
                mennyiseg INT NOT NULL,
                egyseg_ar DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (rendeles_id) REFERENCES rendelesek(id),
                FOREIGN KEY (termek_id) REFERENCES termekek(id)
            )
        ''')
        print("6 tábla OK")

        # Admin felhasználó hozzáadása
        admin_jelszo = generate_password_hash('admin123')
        cursor.execute('''
            INSERT INTO felhasznalok (email, jelszo, nev, szerepkor)
            VALUES ('admin@webaruhaz.hu', %s, 'Admin Felhasználó', 'admin')
            ON CONFLICT (email) DO NOTHING
        ''', (admin_jelszo,))
        print("7 tábla OK")
        
        # Test user hozzáadása
        user_jelszo = generate_password_hash('user123')
        cursor.execute('''
            INSERT INTO felhasznalok (email, jelszo, nev, szerepkor)
            VALUES ('teszt@email.hu', %s, 'Teszt Felhasználó', 'user')
            ON CONFLICT (email) DO NOTHING
        ''', (user_jelszo,))
        print("8 tábla OK")
        
        # Kategóriák hozzáadása
        kategoriak = [
            ('Elektronika', 'Számítógépek, telefonok és egyéb elektronikai cikkek'),
            ('Ruházat', 'Férfi és női ruházati termékek'),
            ('Könyvek', 'Szakkönyvek és szórakoztató irodalom'),
            ('Sport', 'Sporteszközök és sportruházat')
        ]
        
        for kategoria in kategoriak:
            cursor.execute('''
                INSERT INTO kategoriak (nev, leiras)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            ''', kategoria)
        print("9 tábla OK")
        
        # Termékek hozzáadása
        termekek = [
            ('Gaming Laptop', 'Erős gaming laptop NVIDIA grafikus kártyával', 299990, 1, 'https://via.placeholder.com/300x200?text=Gaming+Laptop'),
            ('iPhone 15', 'Legújabb iPhone modell', 389990, 1, 'https://via.placeholder.com/300x200?text=iPhone+15'),
            ('Bluetooth Fejhallgató', 'Vezeték nélküli noise-cancelling fejhallgató', 29990, 1, 'https://via.placeholder.com/300x200?text=Fejhallgato'),
            ('Férfi Póló', 'Pamut póló különböző színekben', 5990, 2, 'https://via.placeholder.com/300x200?text=Ferfi+Polo'),
            ('Női Farmer', 'Klasszikus vágású női farmer', 12990, 2, 'https://via.placeholder.com/300x200?text=Noi+Farmer'),
            ('Python Programozás', 'Python programozási könyv kezdőknek', 8990, 3, 'https://via.placeholder.com/300x200?text=Python+Konyv'),
            ('Futócipő', 'Professzionális futócipő', 24990, 4, 'https://via.placeholder.com/300x200?text=Futocipo'),
            ('Jóga Matrac', 'Antiallergén jóga matrac', 7990, 4, 'https://via.placeholder.com/300x200?text=Joga+Matrac')
        ]
        
        for termek in termekek:
            cursor.execute('''
                INSERT INTO termekek (nev, leiras, ar, kategoria_id, kep_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', termek)
        print("10 tábla OK")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print("Adatbázis sikeresen inicializálva!")
        print("Admin bejelentkezési adatok: admin@webaruhaz.hu / admin123")
        print("Teszt felhasználó adatok: teszt@email.hu / user123")

    except Exception as e:
        print(f"Hiba az adatbázis inicializálásakor: {e}")
    finally:
        try:
            if cursor:
                cursor.close()
        except:
            pass
        try:
            if connection:
                connection.close()
        except:
            pass

# Segédfüggvények
def bejelentkezett_felhasznalo():
    """Aktuálisan bejelentkezett felhasználó lekérése"""
    if 'felhasznalo_id' not in session:
        return None
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return None
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM felhasznalok WHERE id = %s', (session['felhasznalo_id'],))
        felhasznalo = cursor.fetchone()
        
        if felhasznalo:
            return dict(felhasznalo)
        else:
            return None

    except Exception as e:
        print(f"Hiba a bejelentkezett felhasználó lekérésekor: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def admin_szukseges():
    """Ellenőrzi, hogy a felhasználó admin-e"""
    felhasznalo = bejelentkezett_felhasznalo()
    return felhasznalo and felhasznalo['szerepkor'] == 'admin'

def email_kuldese(cimzett, targy, uzenet):
    """E-mail küldése"""
    if not mail_available or not mail:
        print(f"E-mail küldés (nem elérhető): {cimzett} - {targy}")
        return False
    
    try:
        msg = Message(targy, recipients=[cimzett])
        msg.body = uzenet
        mail.send(msg)
        return True
    except Exception as e:
        print(f"E-mail küldési hiba: {e}")
        return False

# Route-ok (URL útvonalak)

@app.route('/')
def fooldal():
    """Főoldal - termékek listázása kategória szűréssel"""
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return render_template('hiba.html')
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # Kategóriák lekérése
    cursor.execute('SELECT * FROM kategoriak ORDER BY nev')
    kategoriak = cursor.fetchall()
    
    # Szűrés kategória szerint
    kategoria_id = request.args.get('kategoria')
    
    if kategoria_id and kategoria_id != 'osszes':
        cursor.execute('''
            SELECT t.*, k.nev as kategoria_nev 
            FROM termekek t 
            LEFT JOIN kategoriak k ON t.kategoria_id = k.id 
            WHERE t.aktiv = TRUE AND t.kategoria_id = %s 
            ORDER BY t.letrehozva DESC
        ''', (kategoria_id,))
    else:
        cursor.execute('''
            SELECT t.*, k.nev as kategoria_nev 
            FROM termekek t 
            LEFT JOIN kategoriak k ON t.kategoria_id = k.id 
            WHERE t.aktiv = TRUE 
            ORDER BY t.letrehozva DESC
        ''')
    
    termekek = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return render_template('fooldal.html', termekek=termekek, kategoriak=kategoriak, kivalasztott_kategoria=kategoria_id)

@app.route('/regisztracio', methods=['GET', 'POST'])
def regisztracio():
    """Felhasználó regisztrációja"""
    if request.method == 'POST':
        email = request.form['email']
        jelszo = request.form['jelszo']
        jelszo_megerosites = request.form['jelszo_megerosites']
        nev = request.form['nev']
        
        # Validáció
        if not email or not jelszo or not nev:
            flash('Minden mező kitöltése kötelező!', 'danger')
            return render_template('regisztracio.html')
        
        if jelszo != jelszo_megerosites:
            flash('A jelszavak nem egyeznek!', 'danger')
            return render_template('regisztracio.html')
        
        if len(jelszo) < 6:
            flash('A jelszó minimum 6 karakter hosszú legyen!', 'danger')
            return render_template('regisztracio.html')
        
        connection = get_db_connection()
        if not connection:
            flash('Adatbázis kapcsolódási hiba!', 'danger')
            return render_template('regisztracio.html')
        
        cursor = connection.cursor()
        
        # Ellenőrizzük, hogy létezik-e már az email
        cursor.execute('SELECT id FROM felhasznalok WHERE email = %s', (email,))
        if cursor.fetchone():
            flash('Ez az email cím már regisztrálva van!', 'danger')
            cursor.close()
            connection.close()
            return render_template('regisztracio.html')
        
        # Új felhasználó létrehozása
        jelszo_hash = generate_password_hash(jelszo)
        cursor.execute('''
            INSERT INTO felhasznalok (email, jelszo, nev, szerepkor)
            VALUES (%s, %s, %s, 'user')
        ''', (email, jelszo_hash, nev))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        flash('Sikeres regisztráció! Most már bejelentkezhetsz.', 'success')
        return redirect(url_for('bejelentkezes'))
    
    return render_template('regisztracio.html')

@app.route('/bejelentkezes', methods=['GET', 'POST'])
def bejelentkezes():
    """Felhasználó bejelentkezése"""
    if request.method == 'POST':
        email = request.form['email']
        jelszo = request.form['jelszo']
        
        connection = get_db_connection()
        if not connection:
            flash('Adatbázis kapcsolódási hiba!', 'danger')
            return render_template('bejelentkezes.html')
        
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM felhasznalok WHERE email = %s', (email,))
        felhasznalo = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if felhasznalo and check_password_hash(felhasznalo['jelszo'], jelszo):
            session['felhasznalo_id'] = felhasznalo['id']
            session['felhasznalo_nev'] = felhasznalo['nev']
            session['admin'] = felhasznalo['szerepkor'] == 'admin'
            flash(f'Üdvözlünk, {felhasznalo["nev"]}!', 'success')
            return redirect(url_for('fooldal'))
        else:
            flash('Hibás email vagy jelszó!', 'danger')
    
    return render_template('bejelentkezes.html')

@app.route('/kijelentkezes')
def kijelentkezes():
    """Felhasználó kijelentkezése"""
    session.clear()
    flash('Sikeresen kijelentkeztél!', 'info')
    return redirect(url_for('fooldal'))

@app.route('/kosarba/<int:termek_id>')
def kosarba(termek_id):
    """Termék hozzáadása a kosárhoz"""
    if 'kosár' not in session:
        session['kosár'] = {}
    
    kosár = session['kosár']
    termek_id_str = str(termek_id)
    
    if termek_id_str in kosár:
        kosár[termek_id_str] += 1
    else:
        kosár[termek_id_str] = 1
    
    session['kosár'] = kosár
    flash('A termék hozzá lett adva a kosárhoz!', 'success')
    return redirect(url_for('fooldal'))

@app.route('/kosar')
def kosar():
    """Kosár tartalmának megjelenítése"""
    if 'kosár' not in session or not session['kosár']:
        return render_template('kosar.html', kosar_tetelek=[], osszeg=0)
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return render_template('kosar.html', kosar_tetelek=[], osszeg=0)
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    kosar_tetelek = []
    osszeg = 0
    
    for termek_id_str, mennyiseg in session['kosár'].items():
        cursor.execute('SELECT * FROM termekek WHERE id = %s AND aktiv = TRUE', (int(termek_id_str),))
        termek = cursor.fetchone()
        if termek:
            tetel_osszeg = termek['ar'] * mennyiseg
            kosar_tetelek.append({
                'termek': termek,
                'mennyiseg': mennyiseg,
                'tetel_osszeg': tetel_osszeg
            })
            osszeg += tetel_osszeg
    
    cursor.close()
    connection.close()
    
    return render_template('kosar.html', kosar_tetelek=kosar_tetelek, osszeg=osszeg)

@app.route('/kosar_torles/<int:termek_id>')
def kosar_torles(termek_id):
    """Termék eltávolítása a kosárból"""
    if 'kosár' in session:
        termek_id_str = str(termek_id)
        if termek_id_str in session['kosár']:
            del session['kosár'][termek_id_str]
            session.modified = True
            flash('A termék el lett távolítva a kosárból!', 'info')
    
    return redirect(url_for('kosar'))

@app.route('/rendeles_leadasa', methods=['POST'])
def rendeles_leadasa():
    """Rendelés leadása"""
    if 'felhasznalo_id' not in session:
        flash('A rendelés leadásához be kell jelentkezned!', 'warning')
        return redirect(url_for('bejelentkezes'))
    
    if 'kosár' not in session or not session['kosár']:
        flash('A kosár üres!', 'warning')
        return redirect(url_for('kosar'))
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return redirect(url_for('kosar'))
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Rendelés összegének kiszámítása
        osszeg = 0
        rendeles_adatok = []
        
        for termek_id_str, mennyiseg in session['kosár'].items():
            cursor.execute('SELECT * FROM termekek WHERE id = %s AND aktiv = TRUE', (int(termek_id_str),))
            termek = cursor.fetchone()
            if termek:
                tetel_osszeg = termek['ar'] * mennyiseg
                osszeg += tetel_osszeg
                rendeles_adatok.append({
                    'termek_id': termek['id'],
                    'termek_nev': termek['nev'],
                    'mennyiseg': mennyiseg,
                    'egyseg_ar': termek['ar'],
                    'tetel_osszeg': tetel_osszeg
                })
        
        if osszeg == 0:
            flash('Nincs érvényes termék a kosárban!', 'danger')
            return redirect(url_for('kosar'))
        
        # Rendelés létrehozása
        cursor.execute('''
            INSERT INTO rendelesek (felhasznalo_id, osszeg)
            VALUES (%s, %s) RETURNING id
        ''', (session['felhasznalo_id'], osszeg))
        rendeles_id = cursor.fetchone()['id']
        
        # Rendelés tételeinek hozzáadása
        for tetel in rendeles_adatok:
            cursor.execute('''
                INSERT INTO rendeles_tetelek (rendeles_id, termek_id, mennyiseg, egyseg_ar)
                VALUES (%s, %s, %s, %s)
            ''', (rendeles_id, tetel['termek_id'], tetel['mennyiseg'], tetel['egyseg_ar']))
        
        connection.commit()
        
        # Felhasználó adatainak lekérése e-mailhez
        cursor.execute('SELECT * FROM felhasznalok WHERE id = %s', (session['felhasznalo_id'],))
        felhasznalo = cursor.fetchone()
        
        # E-mail küldése a felhasználónak
        felhasznalo_uzenet = f"""
        Kedves {felhasznalo['nev']}!
        
        Rendelése sikeresen leadásra került!
        
        Rendelésszám: #{rendeles_id}
        Rendelés összege: {osszeg:,.0f} Ft
        
        Rendelés részletei:
        """
        
        for tetel in rendeles_adatok:
            felhasznalo_uzenet += f"\n- {tetel['termek_nev']} x{tetel['mennyiseg']} - {tetel['tetel_osszeg']:,.0f} Ft"
        
        felhasznalo_uzenet += f"\n\nKöszönjük a vásárlást!\n\nÜdvözlettel,\nWebáruház Csapat"
        
        # Admin e-mail
        admin_uzenet = f"""
        Új rendelés érkezett!
        
        Rendelésszám: #{rendeles_id}
        Vásárló: {felhasznalo['nev']} ({felhasznalo['email']})
        Rendelés összege: {osszeg:,.0f} Ft
        
        Rendelés részletei:
        """
        
        for tetel in rendeles_adatok:
            admin_uzenet += f"\n- {tetel['termek_nev']} x{tetel['mennyiseg']} - {tetel['tetel_osszeg']:,.0f} Ft"
        
        # E-mailek küldése (opcionális, ha be van állítva)
        email_kuldese(felhasznalo['email'], f"Rendelés megerősítés - #{rendeles_id}", felhasznalo_uzenet)
        email_kuldese('admin@webaruhaz.hu', f"Új rendelés - #{rendeles_id}", admin_uzenet)
        
        # Kosár ürítése
        session.pop('kosár', None)
        
        flash(f'Rendelés sikeresen leadva! Rendelésszám: #{rendeles_id}', 'success')
        
    except Exception as e:
        connection.rollback()
        flash(f'Hiba történt a rendelés során: {str(e)}', 'danger')
    finally:
        cursor.close()
        connection.close()
    
    return redirect(url_for('fooldal'))

@app.route('/admin')
def admin_fooldal():
    """Admin főoldal"""
    if not admin_szukseges():
        flash('Admin jogosultság szükséges!', 'danger')
        return redirect(url_for('fooldal'))
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return redirect(url_for('fooldal'))
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # Statisztikák lekérése
    cursor.execute('SELECT COUNT(*) as db FROM termekek WHERE aktiv = TRUE')
    termek_db = cursor.fetchone()['db']
    
    cursor.execute('SELECT COUNT(*) as db FROM rendelesek')
    rendeles_db = cursor.fetchone()['db']
    
    cursor.execute('SELECT SUM(osszeg) as osszeg FROM rendelesek WHERE statusz != %s', ('törölve',))
    result = cursor.fetchone()
    ossz_bevetel = result['osszeg'] or 0
    
    # Legutóbbi rendelések
    cursor.execute('''
        SELECT r.*, f.nev as felhasznalo_nev, f.email as felhasznalo_email
        FROM rendelesek r
        JOIN felhasznalok f ON r.felhasznalo_id = f.id
        ORDER BY r.rendeles_datum DESC
        LIMIT 10
    ''')
    utolso_rendelesek = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template('admin_fooldal.html', 
                         termek_db=termek_db, 
                         rendeles_db=rendeles_db,
                         ossz_bevetel=ossz_bevetel,
                         utolso_rendelesek=utolso_rendelesek)

@app.route('/admin/termekek')
def admin_termekek():
    """Admin termék kezelés"""
    if not admin_szukseges():
        flash('Admin jogosultság szükséges!', 'danger')
        return redirect(url_for('fooldal'))
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return redirect(url_for('fooldal'))
    
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    
    # Termékek és kategóriák lekérése
    cursor.execute('''
        SELECT t.*, k.nev as kategoria_nev 
        FROM termekek t 
        LEFT JOIN kategoriak k ON t.kategoria_id = k.id 
        ORDER BY t.letrehozva DESC
    ''')
    termekek = cursor.fetchall()
    
    cursor.execute('SELECT * FROM kategoriak ORDER BY nev')
    kategoriak = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template('admin_termekek.html', termekek=termekek, kategoriak=kategoriak)

@app.route('/admin/termek_hozzaadas', methods=['POST'])
def termek_hozzaadas():
    """Új termék hozzáadása"""
    if not admin_szukseges():
        flash('Admin jogosultság szükséges!', 'danger')
        return redirect(url_for('fooldal'))
    
    nev = request.form['nev']
    leiras = request.form['leiras']
    ar = request.form['ar']
    kategoria_id = request.form['kategoria_id']
    kep_url = request.form['kep_url']
    
    if not nev or not ar:
        flash('A termék neve és ára kötelező!', 'danger')
        return redirect(url_for('admin_termekek'))
    
    try:
        ar = float(ar)
        if ar <= 0:
            flash('Az ár pozitív szám legyen!', 'danger')
            return redirect(url_for('admin_termekek'))
    except ValueError:
        flash('Hibás ár formátum!', 'danger')
        return redirect(url_for('admin_termekek'))
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return redirect(url_for('admin_termekek'))
    
    cursor = connection.cursor()
    cursor.execute('''
        INSERT INTO termekek (nev, leiras, ar, kategoria_id, kep_url)
        VALUES (%s, %s, %s, %s, %s)
    ''', (nev, leiras, ar, kategoria_id if kategoria_id else None, kep_url))
    
    connection.commit()
    cursor.close()
    connection.close()
    
    flash('Termék sikeresen hozzáadva!', 'success')
    return redirect(url_for('admin_termekek'))

@app.route('/admin/termek_torles/<int:termek_id>')
def termek_torles(termek_id):
    """Termék törlése (deaktiválása)"""
    if not admin_szukseges():
        flash('Admin jogosultság szükséges!', 'danger')
        return redirect(url_for('fooldal'))
    
    connection = get_db_connection()
    if not connection:
        flash('Adatbázis kapcsolódási hiba!', 'danger')
        return redirect(url_for('admin_termekek'))
    
    cursor = connection.cursor()
    cursor.execute('UPDATE termekek SET aktiv = FALSE WHERE id = %s', (termek_id,))
    connection.commit()
    cursor.close()
    connection.close()
    
    flash('Termék sikeresen deaktiválva!', 'success')
    return redirect(url_for('admin_termekek'))

@app.route('/admin/termek_feltoltes', methods=['GET', 'POST'])
def termek_feltoltes():
    """Excel fájl feltöltése és termékek importálása"""
    if not admin_szukseges():
        flash('Admin jogosultság szükséges!', 'danger')
        return redirect(url_for('fooldal'))
    
    if request.method == 'POST':
        # Ellenőrizzük, hogy van-e fájl
        if 'file' not in request.files:
            flash('Nincs fájl kiválasztva!', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        
        # Ellenőrizzük, hogy van-e fájl neve
        if file.filename == '':
            flash('Nincs fájl kiválasztva!', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Fájl mentése
                file.save(filepath)
                
                # Excel fájl beolvasása pandas-szal
                df = pd.read_excel(filepath)
                
                # Kötelező oszlopok ellenőrzése
                required_columns = ['cim', 'leiras', 'kep', 'ar']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    flash(f'Hiányzó oszlopok az Excel fájlban: {", ".join(missing_columns)}', 'danger')
                    os.remove(filepath)  # Fájl törlése
                    return redirect(request.url)
                
                connection = get_db_connection()
                if not connection:
                    flash('Adatbázis kapcsolódási hiba!', 'danger')
                    os.remove(filepath)
                    return redirect(request.url)
                
                cursor = connection.cursor()
                
                sikeres_import = 0
                kihagyott_termekek = 0
                hibas_termekek = 0
                
                for index, row in df.iterrows():
                    try:
                        cim = str(row['cim']).strip() if pd.notna(row['cim']) else None
                        leiras = str(row['leiras']).strip() if pd.notna(row['leiras']) else ""
                        kep_url = str(row['kep']).strip() if pd.notna(row['kep']) else ""
                        ar = float(row['ar']) if pd.notna(row['ar']) else 0
                        
                        # Validáció
                        if not cim or ar <= 0:
                            hibas_termekek += 1
                            continue
                        
                        # Ellenőrizzük, hogy létezik-e már ilyen nevű termék
                        cursor.execute('SELECT id FROM termekek WHERE nev = %s', (cim,))
                        if cursor.fetchone():
                            kihagyott_termekek += 1
                            continue
                        
                        # Termék beszúrása
                        cursor.execute('''
                            INSERT INTO termekek (nev, leiras, ar, kep_url)
                            VALUES (%s, %s, %s, %s)
                        ''', (cim, leiras, ar, kep_url))
                        
                        sikeres_import += 1
                        
                    except Exception as e:
                        print(f"Hiba a {index+2}. sor feldolgozásakor: {e}")
                        hibas_termekek += 1
                        continue
                
                connection.commit()
                cursor.close()
                connection.close()
                
                # Fájl törlése a feltöltés után
                os.remove(filepath)
                
                # Eredmény üzenet
                uzenet = f'Import befejezve! Sikeres: {sikeres_import}, Kihagyott (duplikátum): {kihagyott_termekek}'
                if hibas_termekek > 0:
                    uzenet += f', Hibás: {hibas_termekek}'
                
                if sikeres_import > 0:
                    flash(uzenet, 'success')
                else:
                    flash(uzenet, 'warning')
                
                return redirect(url_for('admin_termekek'))
                
            except Exception as e:
                flash(f'Hiba történt a fájl feldolgozása során: {str(e)}', 'danger')
                # Fájl törlése hiba esetén
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)
        else:
            flash('Csak .xlsx és .xls fájlok engedélyezettek!', 'danger')
            return redirect(request.url)
    
    # GET kérés - feltöltési form megjelenítése
    upload_form_template = '''
    {% extends "base.html" %}
    
    {% block title %}Termékek feltöltése Excel-ből - Admin{% endblock %}
    
    {% block content %}
    <h2>Termékek feltöltése Excel fájlból</h2>
    
    <div class="row">
        <div class="col-md-8">
            <div class="card">
                <div class="card-header">
                    <h5>Excel fájl feltöltése</h5>
                </div>
                <div class="card-body">
                    <div class="alert alert-info">
                        <h6>Excel fájl formátuma:</h6>
                        <p>Az Excel fájlnak tartalmaznia kell az alábbi oszlopokat:</p>
                        <ul>
                            <li><strong>cim</strong> - A termék neve (kötelező)</li>
                            <li><strong>leiras</strong> - A termék leírása</li>
                            <li><strong>kep</strong> - Kép URL címe</li>
                            <li><strong>ar</strong> - A termék ára (kötelező, pozitív szám)</li>
                        </ul>
                        <p><small class="text-muted">Meglévő terméknevek esetén a rendszer kihagyja a duplikátumokat.</small></p>
                    </div>
                    
                    <form method="POST" enctype="multipart/form-data">
                        <div class="mb-3">
                            <label for="file" class="form-label">Válassz Excel fájlt (.xlsx, .xls)</label>
                            <input type="file" class="form-control" id="file" name="file" accept=".xlsx,.xls" required>
                        </div>
                        
                        <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                            <a href="{{ url_for('admin_termekek') }}" class="btn btn-secondary me-md-2">Vissza</a>
                            <button type="submit" class="btn btn-success">Feltöltés és Import</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <div class="col-md-4">
            <div class="card">
                <div class="card-header">
                    <h5>Minta Excel struktúra</h5>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-sm table-bordered">
                            <thead>
                                <tr>
                                    <th>cim</th>
                                    <th>leiras</th>
                                    <th>kep</th>
                                    <th>ar</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>Laptop XYZ</td>
                                    <td>Gaming laptop</td>
                                    <td>http://example.com/kep.jpg</td>
                                    <td>299990</td>
                                </tr>
                                <tr>
                                    <td>Egér ABC</td>
                                    <td>Vezeték nélküli egér</td>
                                    <td>http://example.com/eger.jpg</td>
                                    <td>15990</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="card mt-3">
                <div class="card-header">
                    <h5>Fontos megjegyzések</h5>
                </div>
                <div class="card-body">
                    <ul class="list-unstyled">
                        <li>✅ Maximális fájlméret: 16MB</li>
                        <li>✅ Támogatott formátumok: .xlsx, .xls</li>
                        <li>✅ Duplikált terméknevek automatikusan kihagyásra kerülnek</li>
                        <li>⚠️ Hibás sorok kihagyásra kerülnek</li>
                        <li>⚠️ A fájl feldolgozás után automatikusan törlődik</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    '''
    
    return render_template_string(upload_form_template)

# Alkalmazás indítása
if __name__ == '__main__':
    app.run(debug=True, port=5001)
    # Adatbázis inicializálása
    print("Adatbázis inicializálása...")
    init_database()
    
    print("\n" + "="*50)
    print("Flask Webáruház Excel importtal elkészítve!")
    print("="*50)
    print("\nÚj funkciók:")
    print("✅ Excel fájl feltöltés admin felületen")
    print("✅ Termékek automatikus importálása Excel-ből")
    print("✅ Duplikátum ellenőrzés")
    print("✅ Hibakezelés és visszajelzés")
    print("\nTelepítési követelmények:")
    print("pip install pandas openpyxl")
    print("\nBejelentkezési adatok:")
    print("Admin: admin@webaruhaz.hu / admin123")
    print("User: teszt@email.hu / user123")
    print("\nÚj admin URL: /admin/termek_feltoltes")
    
    # Alkalmazás futtatása
    app.run(debug=True, host='0.0.0.0', port=5000)