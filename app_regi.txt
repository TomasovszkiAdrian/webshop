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
import datetime
import json

# Flask alkalmazás inicializálása
app = Flask(__name__)
app.secret_key = 'titkos_kulcs_123'  # Éles környezetben cseréld ki biztonságosra!

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
        id SERIAL PRIMARY KEY,  -- Egyedi automatikusan növekvő azonosító
        nev VARCHAR(100) NOT NULL,  -- Kategória neve, kötelező
        leiras TEXT  -- Kategória leírása, opcionális
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
                statusz VARCHAR(20) DEFAULT 'feldolgozás alatt' CHECK (statusz IN ('feldolgozás alatt', 'teljesítve', 'törölve')),                rendeles_datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
        # Tesztadatok beszúrása
        
        # Admin felhasználó hozzáadása
     # Tesztadatok beszúrása ON CONFLICT-szal
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
CREATE TABLE IF NOT EXISTS kategoriak (
    id SERIAL PRIMARY KEY,
    nev VARCHAR(100) UNIQUE NOT NULL,
    leiras TEXT
)
''')
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
CREATE TABLE IF NOT EXISTS termekek (
    id SERIAL PRIMARY KEY,
    nev VARCHAR(200) UNIQUE NOT NULL,
    leiras TEXT,
    ar DECIMAL(10,2) NOT NULL,
    kategoria_id INT,
    kep_url VARCHAR(500),
    aktiv BOOLEAN DEFAULT TRUE,
    letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kategoria_id) REFERENCES kategoriak(id)
)
''')
        print("10 tábla OK")
        connection.commit()
        cursor.close()
        connection.close()
        
        print("Adatbázis sikeresen inicializálva!")
        print("Admin bejelentkezési adatok: admin@webaruház.hu / admin123")
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
from psycopg2.extras import RealDictCursor
from flask import session
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
        print("11 tábla OK")
        if felhasznalo:
            return dict(felhasznalo)
        else:
            return None

    except Exception as e:
        # Itt kezelheted az esetleges hibákat (pl. naplózás)
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
    print("12 tábla OK")
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
        print("13 tábla OK")
    else:
        cursor.execute('''
            SELECT t.*, k.nev as kategoria_nev 
            FROM termekek t 
            LEFT JOIN kategoriak k ON t.kategoria_id = k.id 
            WHERE t.aktiv = TRUE 
            ORDER BY t.letrehozva DESC
        ''')
    print("14 tábla OK")
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
        print("15 tábla OK")
        # Új felhasználó létrehozása
        jelszo_hash = generate_password_hash(jelszo)
        cursor.execute('''
            INSERT INTO felhasznalok (email, jelszo, nev, szerepkor)
            VALUES (%s, %s, %s, 'user')
        ''', (email, jelszo_hash, nev))
        print("16 tábla OK")
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
        print("17 tábla OK")
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
    print("18 tábla OK")
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
        print("19 tábla OK")
        if osszeg == 0:
            flash('Nincs érvényes termék a kosárban!', 'danger')
            return redirect(url_for('kosar'))
        
        # Rendelés létrehozása
        cursor.execute('''
            INSERT INTO rendelesek (felhasznalo_id, osszeg)
            VALUES (%s, %s) RETURNING id
        ''', (session['felhasznalo_id'], osszeg))
        print("20 tábla OK")
        rendeles_id = cursor.fetchone()['id']
        
        # Rendelés tételeinek hozzáadása
        for tetel in rendeles_adatok:
            cursor.execute('''
                INSERT INTO rendeles_tetelek (rendeles_id, termek_id, mennyiseg, egyseg_ar)
                VALUES (%s, %s, %s, %s)
            ''', (rendeles_id, tetel['termek_id'], tetel['mennyiseg'], tetel['egyseg_ar']))
        print("21 tábla OK")
        connection.commit()
        
        # Felhasználó adatainak lekérése e-mailhez
        cursor.execute('SELECT * FROM felhasznalok WHERE id = %s', (session['felhasznalo_id'],))
        felhasznalo = cursor.fetchone()
        print("22 tábla OK")
        # Felhasználó adatainak lekérése e-mailhez
        cursor.execute('SELECT * FROM felhasznalok WHERE id = %s', (session['felhasznalo_id'],))
        felhasznalo = cursor.fetchone()
        print("23 tábla OK")
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
        email_kuldese('admin@webaruház.hu', f"Új rendelés - #{rendeles_id}", admin_uzenet)
        
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
    
    cursor = connection.cursor(dictionary=True)
    
    # Statisztikák lekérése
    cursor.execute('SELECT COUNT(*) as db FROM termekek WHERE aktiv = TRUE')
    termek_db = cursor.fetchone()['db']
    print("24 tábla OK")
    cursor.execute('SELECT COUNT(*) as db FROM rendelesek')
    rendeles_db = cursor.fetchone()['db']
    print("25 tábla OK")
    cursor.execute('SELECT SUM(osszeg) as osszeg FROM rendelesek WHERE statusz != "törölve"')
    result = cursor.fetchone()
    ossz_bevetel = result['osszeg'] or 0
    print("26 tábla OK")
    # Legutóbbi rendelések
    cursor.execute('''
        SELECT r.*, f.nev as felhasznalo_nev, f.email as felhasznalo_email
        FROM rendelesek r
        JOIN felhasznalok f ON r.felhasznalo_id = f.id
        ORDER BY r.rendeles_datum DESC
        LIMIT 10
    ''')
    print("27 tábla OK")
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
    
    cursor = connection.cursor(dictionary=True)
    
    # Termékek és kategóriák lekérése
    cursor.execute('''
        SELECT t.*, k.nev as kategoria_nev 
        FROM termekek t 
        LEFT JOIN kategoriak k ON t.kategoria_id = k.id 
        ORDER BY t.letrehozva DESC
    ''')
    print("28 tábla OK")
    termekek = cursor.fetchall()
    
    cursor.execute('SELECT * FROM kategoriak ORDER BY nev')
    kategoriak = cursor.fetchall()
    print("29 tábla OK")
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
    print("30 tábla OK")
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
    print("31 tábla OK")
    flash('Termék sikeresen deaktiválva!', 'success')
    return redirect(url_for('admin_termekek'))

# Template-ek (HTML sablonok) - ezeket külön fájlokba kell menteni a templates/ mappába

templates = {
    'base.html': '''<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Webáruház{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .product-image { height: 200px; object-fit: cover; }
        .navbar-brand { font-weight: bold; }
        .footer { background-color: #f8f9fa; margin-top: 50px; }
        .card-img-top { height: 200px; object-fit: cover; }
    </style>
</head>
<body>
    <!-- Navigációs sáv -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('fooldal') }}">🛒 Webáruház</a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('fooldal') }}">Főoldal</a>
                    </li>
                    {% if session.admin %}
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('admin_fooldal') }}">Admin</a>
                    </li>
                    {% endif %}
                </ul>
                
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('kosar') }}">
                            🛒 Kosár 
                            {% if session.kosár %}
                                <span class="badge bg-warning">{{ session.kosár.values() | sum }}</span>
                            {% endif %}
                        </a>
                    </li>
                    
                    {% if session.felhasznalo_id %}
                        <li class="nav-item">
                            <span class="navbar-text me-3">Üdv, {{ session.felhasznalo_nev }}!</span>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('kijelentkezes') }}">Kijelentkezés</a>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('bejelentkezes') }}">Bejelentkezés</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('regisztracio') }}">Regisztráció</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- Flash üzenetek -->
    <div class="container mt-3">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <!-- Fő tartalom -->
    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>

    <!-- Lábléc -->
    <footer class="footer mt-5 py-4 text-center">
        <div class="container">
            <p>&copy; 2024 Webáruház. Minden jog fenntartva.</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>''',

    'fooldal.html': '''{% extends "base.html" %}

{% block title %}Főoldal - Webáruház{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-3">
        <h5>Kategóriák</h5>
        <div class="list-group">
            <a href="{{ url_for('fooldal') }}" 
               class="list-group-item list-group-item-action {% if not kivalasztott_kategoria or kivalasztott_kategoria == 'osszes' %}active{% endif %}">
                Összes termék
            </a>
            {% for kategoria in kategoriak %}
            <a href="{{ url_for('fooldal', kategoria=kategoria.id) }}" 
               class="list-group-item list-group-item-action {% if kivalasztott_kategoria|string == kategoria.id|string %}active{% endif %}">
                {{ kategoria.nev }}
            </a>
            {% endfor %}
        </div>
    </div>
    
    <div class="col-md-9">
        <h2>Termékeink</h2>
        {% if not termekek %}
            <div class="alert alert-info">
                <h4>Nincs megjeleníthető termék</h4>
                <p>Jelenleg nincs termék a kiválasztott kategóriában.</p>
            </div>
        {% else %}
            <div class="row">
                {% for termek in termekek %}
                <div class="col-md-4 mb-4">
                    <div class="card h-100">
                        {% if termek.kep_url %}
                            <img src="{{ termek.kep_url }}" class="card-img-top" alt="{{ termek.nev }}">
                        {% endif %}
                        <div class="card-body">
                            <h5 class="card-title">{{ termek.nev }}</h5>
                            <p class="card-text">{{ termek.leiras[:100] }}{% if termek.leiras|length > 100 %}...{% endif %}</p>
                            <p class="card-text">
                                <small class="text-muted">{{ termek.kategoria_nev or 'Kategória nélkül' }}</small>
                            </p>
                        </div>
                        <div class="card-footer">
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="h5 text-primary">{{ "{:,.0f}".format(termek.ar) }} Ft</span>
                                <a href="{{ url_for('kosarba', termek_id=termek.id) }}" class="btn btn-success">
                                    Kosárba
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}''',

    'kosar.html': '''{% extends "base.html" %}

{% block title %}Kosár - Webáruház{% endblock %}

{% block content %}
<h2>Kosaram</h2>

{% if not kosar_tetelek %}
    <div class="alert alert-info">
        <h4>A kosár üres</h4>
        <p>Még nem adtál hozzá terméket a kosárhoz.</p>
        <a href="{{ url_for('fooldal') }}" class="btn btn-primary">Vásárlás folytatása</a>
    </div>
{% else %}
    <div class="table-responsive">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Termék</th>
                    <th>Ár</th>
                    <th>Mennyiség</th>
                    <th>Összesen</th>
                    <th>Művelet</th>
                </tr>
            </thead>
            <tbody>
                {% for tetel in kosar_tetelek %}
                <tr>
                    <td>
                        <div class="d-flex align-items-center">
                            {% if tetel.termek.kep_url %}
                                <img src="{{ tetel.termek.kep_url }}" class="me-3" style="width: 60px; height: 60px; object-fit: cover;" alt="{{ tetel.termek.nev }}">
                            {% endif %}
                            <div>
                                <h6 class="mb-0">{{ tetel.termek.nev }}</h6>
                                <small class="text-muted">{{ tetel.termek.leiras[:50] }}...</small>
                            </div>
                        </div>
                    </td>
                    <td>{{ "{:,.0f}".format(tetel.termek.ar) }} Ft</td>
                    <td>{{ tetel.mennyiseg }} db</td>
                    <td><strong>{{ "{:,.0f}".format(tetel.tetel_osszeg) }} Ft</strong></td>
                    <td>
                        <a href="{{ url_for('kosar_torles', termek_id=tetel.termek.id) }}" 
                           class="btn btn-sm btn-outline-danger"
                           onclick="return confirm('Biztosan törölni szeretnéd ezt a terméket a kosárból?')">
                            Törlés
                        </a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
            <tfoot>
                <tr class="table-active">
                    <td colspan="3"><strong>Végösszeg:</strong></td>
                    <td><strong class="h5 text-success">{{ "{:,.0f}".format(osszeg) }} Ft</strong></td>
                    <td></td>
                </tr>
            </tfoot>
        </table>
    </div>
    
    <div class="row mt-4">
        <div class="col-md-6">
            <a href="{{ url_for('fooldal') }}" class="btn btn-secondary">Vásárlás folytatása</a>
        </div>
        <div class="col-md-6 text-end">
            {% if session.felhasznalo_id %}
                <form method="POST" action="{{ url_for('rendeles_leadasa') }}" style="display: inline;">
                    <button type="submit" class="btn btn-success btn-lg"
                            onclick="return confirm('Biztosan le szeretnéd adni a rendelést?')">
                        Rendelés leadása
                    </button>
                </form>
            {% else %}
                <p class="text-muted mb-2">A rendelés leadásához jelentkezz be!</p>
                <a href="{{ url_for('bejelentkezes') }}" class="btn btn-primary">Bejelentkezés</a>
            {% endif %}
        </div>
    </div>
{% endif %}
{% endblock %}''',

    'bejelentkezes.html': '''{% extends "base.html" %}

{% block title %}Bejelentkezés - Webáruház{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4 class="mb-0">Bejelentkezés</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="email" class="form-label">E-mail cím</label>
                        <input type="email" class="form-control" id="email" name="email" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="jelszo" class="form-label">Jelszó</label>
                        <input type="password" class="form-control" id="jelszo" name="jelszo" required>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Bejelentkezés</button>
                    </div>
                </form>
                
                <div class="text-center mt-3">
                    <p>Még nincs fiókod? <a href="{{ url_for('regisztracio') }}">Regisztráció</a></p>
                </div>
                
                <div class="mt-4 p-3 bg-light rounded">
                    <h6>Teszt bejelentkezési adatok:</h6>
                    <p class="mb-1"><strong>Admin:</strong> admin@webaruház.hu / admin123</p>
                    <p class="mb-0"><strong>Felhasználó:</strong> teszt@email.hu / user123</p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}''',

    'regisztracio.html': '''{% extends "base.html" %}

{% block title %}Regisztráció - Webáruház{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h4 class="mb-0">Regisztráció</h4>
            </div>
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="nev" class="form-label">Teljes név</label>
                        <input type="text" class="form-control" id="nev" name="nev" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="email" class="form-label">E-mail cím</label>
                        <input type="email" class="form-control" id="email" name="email" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="jelszo" class="form-label">Jelszó</label>
                        <input type="password" class="form-control" id="jelszo" name="jelszo" required>
                        <div class="form-text">Minimum 6 karakter</div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="jelszo_megerosites" class="form-label">Jelszó megerősítése</label>
                        <input type="password" class="form-control" id="jelszo_megerosites" name="jelszo_megerosites" required>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-success">Regisztráció</button>
                    </div>
                </form>
                
                <div class="text-center mt-3">
                    <p>Van már fiókod? <a href="{{ url_for('bejelentkezes') }}">Bejelentkezés</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}''',

    'admin_fooldal.html': '''{% extends "base.html" %}

{% block title %}Admin - Webáruház{% endblock %}

{% block content %}
<h2>Admin Irányítópult</h2>

<div class="row mb-4">
    <div class="col-md-4">
        <div class="card text-white bg-primary">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4 class="card-title">{{ termek_db }}</h4>
                        <p class="card-text">Aktív termékek</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-boxes fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card text-white bg-success">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4 class="card-title">{{ rendeles_db }}</h4>
                        <p class="card-text">Összes rendelés</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-shopping-cart fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card text-white bg-info">
            <div class="card-body">
                <div class="d-flex justify-content-between">
                    <div>
                        <h4 class="card-title">{{ "{:,.0f}".format(ossz_bevetel) }} Ft</h4>
                        <p class="card-text">Összes bevétel</p>
                    </div>
                    <div class="align-self-center">
                        <i class="fas fa-money-bill-wave fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5>Gyors műveletek</h5>
            </div>
            <div class="card-body">
                <a href="{{ url_for('admin_termekek') }}" class="btn btn-primary mb-2 d-block">
                    Termékek kezelése
                </a>
                <a href="{{ url_for('fooldal') }}" class="btn btn-secondary d-block">
                    Webáruház megtekintése
                </a>
            </div>
        </div>
    </div>
    
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5>Legutóbbi rendelések</h5>
            </div>
            <div class="card-body">
                {% if not utolso_rendelesek %}
                    <p class="text-muted">Még nincsenek rendelések.</p>
                {% else %}
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Vásárló</th>
                                    <th>Összeg</th>
                                    <th>Dátum</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for rendeles in utolso_rendelesek %}
                                <tr>
                                    <td>{{ rendeles.id }}</td>
                                    <td>{{ rendeles.felhasznalo_nev }}</td>
                                    <td>{{ "{:,.0f}".format(rendeles.osszeg) }} Ft</td>
                                    <td>{{ rendeles.rendeles_datum.strftime('%m-%d %H:%M') }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}''',

    'admin_termekek.html': '''{% extends "base.html" %}

{% block title %}Termékek kezelése - Admin{% endblock %}

{% block content %}
<h2>Termékek kezelése</h2>

<div class="row">
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5>Új termék hozzáadása</h5>
            </div>
            <div class="card-body">
                <form method="POST" action="{{ url_for('termek_hozzaadas') }}">
                    <div class="mb-3">
                        <label for="nev" class="form-label">Termék neve *</label>
                        <input type="text" class="form-control" id="nev" name="nev" required>
                    </div>
                    
                    <div class="mb-3">
                        <label for="leiras" class="form-label">Leírás</label>
                        <textarea class="form-control" id="leiras" name="leiras" rows="3"></textarea>
                    </div>
                    
                    <div class="mb-3">
                        <label for="ar" class="form-label">Ár (Ft) *</label>
                        <input type="number" class="form-control" id="ar" name="ar" required min="0" step="1">
                    </div>
                    
                    <div class="mb-3">
                        <label for="kategoria_id" class="form-label">Kategória</label>
                        <select class="form-control" id="kategoria_id" name="kategoria_id">
                            <option value="">Válassz kategóriát</option>
                            {% for kategoria in kategoriak %}
                                <option value="{{ kategoria.id }}">{{ kategoria.nev }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="kep_url" class="form-label">Kép URL</label>
                        <input type="url" class="form-control" id="kep_url" name="kep_url" 
                               placeholder="https://example.com/kep.jpg">
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-success">Termék hozzáadása</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h5>Meglévő termékek</h5>
            </div>
            <div class="card-body">
                {% if not termekek %}
                    <p class="text-muted">Még nincsenek termékek az adatbázisban.</p>
                {% else %}
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Név</th>
                                    <th>Kategória</th>
                                    <th>Ár</th>
                                    <th>Állapot</th>
                                    <th>Művelet</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for termek in termekek %}
                                <tr class="{% if not termek.aktiv %}table-secondary{% endif %}">
                                    <td>{{ termek.id }}</td>
                                    <td>
                                        <div class="d-flex align-items-center">
                                            {% if termek.kep_url %}
                                                <img src="{{ termek.kep_url }}" class="me-2" style="width: 40px; height: 40px; object-fit: cover;" alt="{{ termek.nev }}">
                                            {% endif %}
                                            <div>
                                                <strong>{{ termek.nev }}</strong>
                                                {% if termek.leiras %}
                                                    <br><small class="text-muted">{{ termek.leiras[:50] }}...</small>
                                                {% endif %}
                                            </div>
                                        </div>
                                    </td>
                                    <td>{{ termek.kategoria_nev or 'Nincs' }}</td>
                                    <td>{{ "{:,.0f}".format(termek.ar) }} Ft</td>
                                    <td>
                                        {% if termek.aktiv %}
                                            <span class="badge bg-success">Aktív</span>
                                        {% else %}
                                            <span class="badge bg-secondary">Inaktív</span>
                                        {% endif %}
                                    </td>
                                    <td>
                                        {% if termek.aktiv %}
                                            <a href="{{ url_for('termek_torles', termek_id=termek.id) }}" 
                                               class="btn btn-sm btn-outline-danger"
                                               onclick="return confirm('Biztosan deaktiválni szeretnéd ezt a terméket?')">
                                                Deaktiválás
                                            </a>
                                        {% else %}
                                            <span class="text-muted">Deaktivált</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<div class="mt-4">
    <a href="{{ url_for('admin_fooldal') }}" class="btn btn-secondary">Vissza az admin főoldalra</a>
</div>
{% endblock %}''',

    'hiba.html': '''{% extends "base.html" %}

{% block title %}Hiba - Webáruház{% endblock %}

{% block content %}
<div class="text-center">
    <h1 class="display-4">Hiba történt!</h1>
    <p class="lead">Sajnos valami hiba történt az oldal betöltése közben.</p>
    <a href="{{ url_for('fooldal') }}" class="btn btn-primary">Vissza a főoldalra</a>
</div>
{% endblock %}'''
}

# Alkalmazás indítása
if __name__ == "__main__":
    app.run(port=5001, debug=True)
    # Adatbázis inicializálása
    print("Adatbázis inicializálása...")
    init_database()
    """"
    print("\n" + "="*50)
    print("Flask Webáruház elkészítve!")
    print("="*50)
    print("\nTelepítési lépések:")
    print("1. Telepítsd a szükséges csomagokat:")
    print("\n2. Hozd létre a 'templates' mappát a Python fájl mellett")
    print("\n3. Mentsd el az alábbi HTML template-eket a templates/ mappába:")
    """
    for filename, content in templates.items():
        print(f"   - {filename}")
        # Itt írd ki a fájlokat vagy használj kódot a mentésükre
        try:
            import os
            if not os.path.exists('templates'):
                os.makedirs('templates')
            with open(f'templates/{filename}', 'w', encoding='utf-8') as f:
                f.write(content)
        except:
            pass
    """
    print("5. Opcionálisan konfiguráld az e-mail küldést")
    print("6. Indítsd el: python app.py")
    print("\nBejelentkezési adatok:")
    print("Admin: admin@webaruház.hu / admin123")
    print("User: teszt@email.hu / user123")
    print("\nWebáruház funkciók:")
    print("✅ Felhasználó regisztráció/bejelentkezés")
    print("✅ Termékek böngészése kategóriák szerint")
    print("✅ Kosár kezelése")
    print("✅ Rendelés leadása")
    print("✅ Admin termék kezelése")
    print("✅ E-mail értesítések")
    print("✅ Bootstrap design")
    """
    # Alkalmazás futtatása
    app.run(debug=True, host='0.0.0.0', port=5000)