from flask import Flask, render_template_string, request, jsonify, send_file
import os
from datetime import date, datetime, timedelta
import json
import sys
import sqlite3
from io import BytesIO

app = Flask(__name__)

# Загружаем HTML-код
# Получаем директорию, где находится app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, 'report_generator.html')

# Проверяем существование файла
if not os.path.exists(HTML_FILE):
    print(f"❌ Файл не найден: {HTML_FILE}")
    print(f"📍 Текущая директория: {BASE_DIR}")
    print(f"📁 Содержимое директории: {os.listdir(BASE_DIR)}")
    sys.exit(1)

# Загружаем HTML-код
with open(HTML_FILE, 'r', encoding='utf-8') as f:
    HTML_TEMPLATE = f.read()

print(f"✅ HTML файл загружен: {HTML_FILE}")

# Инициализация базы данных
def init_db():
    """Инициализация базы данных при первом запуске"""
    conn = sqlite3.connect('habits.db')
    cursor = conn.cursor()
    
    # Таблица привычек (справочник)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            default_quantity REAL,
            unit TEXT,
            i REAL DEFAULT 0.0,
            s REAL DEFAULT 0.0,
            w REAL DEFAULT 0.0,
            e REAL DEFAULT 0.0,
            c REAL DEFAULT 0.0,
            h REAL DEFAULT 0.0,
            st REAL DEFAULT 0.0,
            money REAL DEFAULT 0.0,
            is_composite BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, category)
        )
    ''')
    
    # Таблица подзадач для составных привычек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS habit_subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            default_quantity REAL,
            unit TEXT,
            i REAL DEFAULT 0.0,
            s REAL DEFAULT 0.0,
            w REAL DEFAULT 0.0,
            e REAL DEFAULT 0.0,
            c REAL DEFAULT 0.0,
            h REAL DEFAULT 0.0,
            st REAL DEFAULT 0.0,
            money REAL DEFAULT 0.0,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (habit_id) REFERENCES habits (id) ON DELETE CASCADE
        )
    ''')
    
    # Таблица выполненных привычек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS completed_habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            subtask_id INTEGER,
            date DATE NOT NULL,
            quantity REAL,
            success BOOLEAN DEFAULT 1,
            i REAL DEFAULT 0.0,
            s REAL DEFAULT 0.0,
            w REAL DEFAULT 0.0,
            e REAL DEFAULT 0.0,
            c REAL DEFAULT 0.0,
            h REAL DEFAULT 0.0,
            st REAL DEFAULT 0.0,
            money REAL DEFAULT 0.0,
            notes TEXT,
            day_number INTEGER,
            state TEXT,
            emotion_morning TEXT,
            thoughts TEXT,
            FOREIGN KEY (habit_id) REFERENCES habits (id),
            FOREIGN KEY (subtask_id) REFERENCES habit_subtasks (id),
            UNIQUE(habit_id, subtask_id, date)
        )
    ''')
    
    # Таблица дней дисциплины
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discipline_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            day_number INTEGER NOT NULL,
            state TEXT,
            emotion_morning TEXT,
            thoughts TEXT,
            total_i REAL DEFAULT 0.0,
            total_s REAL DEFAULT 0.0,
            total_w REAL DEFAULT 0.0,
            total_e REAL DEFAULT 0.0,
            total_c REAL DEFAULT 0.0,
            total_h REAL DEFAULT 0.0,
            total_st REAL DEFAULT 0.0,
            total_money REAL DEFAULT 0.0,
            completed_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица стриков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS streaks (
            habit_id INTEGER NOT NULL,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_date DATE,
            FOREIGN KEY (habit_id) REFERENCES habits (id)
        )
    ''')

    # Таблица сочетаний (combinations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS combinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            habit_a INTEGER NOT NULL,
            habit_b INTEGER NOT NULL,
            i REAL DEFAULT 0.0,
            s REAL DEFAULT 0.0,
            w REAL DEFAULT 0.0,
            e REAL DEFAULT 0.0,
            c REAL DEFAULT 0.0,
            h REAL DEFAULT 0.0,
            st REAL DEFAULT 0.0,
            money REAL DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(habit_a, habit_b),
            FOREIGN KEY (habit_a) REFERENCES habits (id) ON DELETE CASCADE,
            FOREIGN KEY (habit_b) REFERENCES habits (id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_combinations_habits ON combinations(habit_a, habit_b)')
    
    # Индексы
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_streaks_habit ON streaks(habit_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_completed_date ON completed_habits(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_completed_habit ON completed_habits(habit_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_habits_category ON habits(category)')
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    """Главная страница с генератором отчетов"""
    return render_template_string(HTML_TEMPLATE)

# ============ API для работы с привычками ============

@app.route('/api/habits', methods=['GET'])
def get_habits():
    """Получение списка всех привычек из справочника"""
    try:
        category = request.args.get('category')
        search = request.args.get('search', '')
        
        conn = sqlite3.connect('habits.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM habits WHERE is_active = 1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.append(f"%{search}%")
            params.append(f"%{search}%")
        
        query += " ORDER BY category, name"
        
        cursor.execute(query, params)
        habits = [dict(row) for row in cursor.fetchall()]
        
        # Загружаем подзадачи для составных привычек
        for habit in habits:
            if habit['is_composite']:
                cursor.execute('SELECT * FROM habit_subtasks WHERE habit_id = ? ORDER BY order_index', (habit['id'],))
                habit['subtasks'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({'status': 'success', 'data': habits})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/habits/categories', methods=['GET'])
def get_categories():
    """Получение списка всех категорий"""
    try:
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT category FROM habits WHERE is_active = 1 ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({'status': 'success', 'data': categories})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/combinations', methods=['GET'])
def get_combinations():
    try:
        conn = sqlite3.connect('habits.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, ha.name as name_a, hb.name as name_b
            FROM combinations c
            LEFT JOIN habits ha ON c.habit_a = ha.id
            LEFT JOIN habits hb ON c.habit_b = hb.id
            WHERE c.is_active = 1
            ORDER BY c.id DESC
        ''')
        combos = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'status': 'success', 'data': combos})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/combinations', methods=['POST'])
def create_combination():
    try:
        data = request.json
        a = int(data.get('habit_a'))
        b = int(data.get('habit_b'))
        if a == b:
            return jsonify({'status':'error','message':'habit_a and habit_b must be different'}), 400
        # упорядочим (habit_a < habit_b)
        if a > b:
            a, b = b, a

        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO combinations (name, habit_a, habit_b, i, s, w, e, c, h, st, money, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            a, b,
            float(data.get('i', 0.0)),
            float(data.get('s', 0.0)),
            float(data.get('w', 0.0)),
            float(data.get('e', 0.0)),
            float(data.get('c', 0.0)),
            float(data.get('h', 0.0)),
            float(data.get('st', 0.0)),
            float(data.get('money', 0.0)),
            1
        ))
        conn.commit()
        combo_id = cursor.lastrowid
        conn.close()
        return jsonify({'status':'success','id': combo_id})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500


@app.route('/api/habits', methods=['POST'])
def add_habit():
    """Добавление новой привычки в справочник"""
    try:
        data = request.json
        
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже такая привычка
        cursor.execute('SELECT id FROM habits WHERE name = ? AND category = ?', 
                      (data['name'], data.get('category', 'Без категории')))
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'message': 'Привычка уже существует'}), 400
        
        # Добавляем привычку
        cursor.execute('''
            INSERT INTO habits 
            (name, category, description, default_quantity, unit, 
             i, s, w, e, c, h, st, money, is_composite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data.get('category', 'Без категории'),
            data.get('description'),
            data.get('default_quantity'),
            data.get('unit'),
            data.get('i', 0.0),
            data.get('s', 0.0),
            data.get('w', 0.0),
            data.get('e', 0.0),
            data.get('c', 0.0),
            data.get('h', 0.0),
            data.get('st', 0.0),
            data.get('money', 0.0),
            1 if data.get('is_composite') else 0
        ))
        
        habit_id = cursor.lastrowid
        
        # Если привычка составная, добавляем подзадачи
        if data.get('is_composite') and data.get('subtasks'):
            for i, subtask in enumerate(data['subtasks']):
                cursor.execute('''
                    INSERT INTO habit_subtasks 
                    (habit_id, name, default_quantity, unit, i, s, w, e, c, h, st, money, order_index)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    habit_id,
                    subtask['name'],
                    subtask.get('default_quantity'),
                    subtask.get('unit'),
                    subtask.get('i', 0.0),
                    subtask.get('s', 0.0),
                    subtask.get('w', 0.0),
                    subtask.get('e', 0.0),
                    subtask.get('c', 0.0),
                    subtask.get('h', 0.0),
                    subtask.get('st', 0.0),
                    subtask.get('money', 0.0),
                    i
                ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'habit_id': habit_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/habits/<int:habit_id>', methods=['PUT'])
def update_habit(habit_id):
    """Обновление привычки в справочнике"""
    try:
        data = request.json
        
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        # Обновляем основные данные
        cursor.execute('''
            UPDATE habits SET
                name = COALESCE(?, name),
                category = COALESCE(?, category),
                description = COALESCE(?, description),
                default_quantity = COALESCE(?, default_quantity),
                unit = COALESCE(?, unit),
                i = COALESCE(?, i),
                s = COALESCE(?, s),
                w = COALESCE(?, w),
                e = COALESCE(?, e),
                c = COALESCE(?, c),
                h = COALESCE(?, h),
                st = COALESCE(?, st),
                money = COALESCE(?, money),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('name'),
            data.get('category'),
            data.get('description'),
            data.get('default_quantity'),
            data.get('unit'),
            data.get('i'),
            data.get('s'),
            data.get('w'),
            data.get('e'),
            data.get('c'),
            data.get('h'),
            data.get('st'),
            data.get('money'),
            habit_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/habits/<int:habit_id>', methods=['DELETE'])
def delete_habit(habit_id):
    """Удаление привычки из справочника"""
    try:
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        # Мягкое удаление
        cursor.execute('UPDATE habits SET is_active = 0 WHERE id = ?', (habit_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============ API для работы с выполненными привычками ============

def update_streak(habit_id, date_str, success):
    """Обновление/создание стрика для привычки"""
    try:
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()

        # Попробуем получить существующий стрик
        cursor.execute('SELECT habit_id, current_streak, longest_streak, last_date FROM streaks WHERE habit_id = ?', (habit_id,))
        streak = cursor.fetchone()

        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if not streak:
            # Создаем запись даже если success=False (чтобы клиент видел нули)
            if success:
                cursor.execute('''
                    INSERT OR REPLACE INTO streaks (habit_id, current_streak, longest_streak, last_date)
                    VALUES (?, ?, ?, ?)
                ''', (habit_id, 1, 1, date_str))
            else:
                cursor.execute('''
                    INSERT OR REPLACE INTO streaks (habit_id, current_streak, longest_streak, last_date)
                    VALUES (?, ?, ?, ?)
                ''', (habit_id, 0, 0, None))
        else:
            # streak: (habit_id, current_streak, longest_streak, last_date)
            last_date = None
            try:
                last_date = datetime.strptime(streak[3], '%Y-%m-%d').date() if streak[3] else None
            except Exception:
                last_date = None

            current_streak = int(streak[1] or 0)
            longest_streak = int(streak[2] or 0)

            if success:
                if last_date and (current_date - last_date).days == 1:
                    current_streak = current_streak + 1
                else:
                    # если предыдущая дата не была вчерашней — стартуем заново
                    current_streak = 1

                if current_streak > longest_streak:
                    longest_streak = current_streak

                cursor.execute('''
                    UPDATE streaks SET 
                        current_streak = ?,
                        longest_streak = ?,
                        last_date = ?
                    WHERE habit_id = ?
                ''', (current_streak, longest_streak, date_str, habit_id))
            else:
                # сбрасываем current_streak, не трогаем longest
                cursor.execute('''
                    UPDATE streaks SET
                        current_streak = ? 
                    WHERE habit_id = ?
                ''', (0, habit_id))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating streak: {e}")


@app.route('/api/completions', methods=['POST'])
def save_completions():
    """Сохранение выполненных привычек за день (и пересчёт стриков)"""
    try:
        data = request.json
        day_date = data.get('date', date.today().isoformat())

        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()

        # Удаляем старые записи за этот день
        cursor.execute('DELETE FROM completed_habits WHERE date = ?', (day_date,))

        # Сохраняем каждую привычку (только если есть habit_id)
        for habit in data.get('habits', []):
            if not habit.get('habit_id'):
                # пропускаем записи без habit_id, логируем
                print('Skipping habit without habit_id:', habit)
                continue

            cursor.execute('''
                INSERT INTO completed_habits 
                (habit_id, date, quantity, success, i, s, w, e, c, h, st, money, 
                 day_number, state, emotion_morning, thoughts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                habit.get('habit_id'),
                day_date,
                habit.get('quantity'),
                1 if habit.get('success') else 0,
                habit.get('i', 0.0),
                habit.get('s', 0.0),
                habit.get('w', 0.0),
                habit.get('e', 0.0),
                habit.get('c', 0.0),
                habit.get('h', 0.0),
                habit.get('st', 0.0),
                habit.get('money', 0.0),
                data.get('day_number'),
                data.get('state'),
                data.get('emotion_morning'),
                data.get('thoughts')
            ))

        # ---- вычислить и применить бонусы сочетаний ----
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT habit_id FROM completed_habits WHERE date = ? AND success = 1', (day_date,))
            done_ids = set([r['habit_id'] for r in cursor.fetchall()])

            if done_ids:
                cursor.execute('SELECT * FROM combinations WHERE is_active = 1')
                combos = [dict(r) for r in cursor.fetchall()]
                combo_bonus = {'I':0.0,'S':0.0,'W':0.0,'E':0.0,'C':0.0,'H':0.0,'ST':0.0,'$':0.0}
                for c in combos:
                    if c['habit_a'] in done_ids and c['habit_b'] in done_ids:
                        combo_bonus['I'] += c.get('i', 0.0) or 0.0
                        combo_bonus['S'] += c.get('s', 0.0) or 0.0
                        combo_bonus['W'] += c.get('w', 0.0) or 0.0
                        combo_bonus['E'] += c.get('e', 0.0) or 0.0
                        combo_bonus['C'] += c.get('c', 0.0) or 0.0
                        combo_bonus['H'] += c.get('h', 0.0) or 0.0
                        combo_bonus['ST'] += c.get('st', 0.0) or 0.0
                        combo_bonus['$'] += c.get('money', 0.0) or 0.0

                # добавим бонусы сочетаний к totals, если переданы totals или инициализируем
                totals = data.get('totals', {})
                totals = {
                    'I': totals.get('I', 0.0) + combo_bonus['I'],
                    'S': totals.get('S', 0.0) + combo_bonus['S'],
                    'W': totals.get('W', 0.0) + combo_bonus['W'],
                    'E': totals.get('E', 0.0) + combo_bonus['E'],
                    'C': totals.get('C', 0.0) + combo_bonus['C'],
                    'H': totals.get('H', 0.0) + combo_bonus['H'],
                    'ST': totals.get('ST', 0.0) + combo_bonus['ST'],
                    '$': totals.get('$', 0.0) + combo_bonus['$']
                }
                # запишем обратно в data, чтобы ниже вставка использовала обновлённые totals
                data['totals'] = totals
        except Exception as e:
            print('Error applying combinations bonuses:', e)

        # Сохраняем статистику дня (и приводим к числам)
        totals = data.get('totals', {}) or {}
        # Убедимся, что все ключи присутствуют и числовые
        for _k in ('I','S','W','E','C','H','ST','$'):
            try:
                totals[_k] = float(totals.get(_k, 0) or 0.0)
            except Exception:
                totals[_k] = 0.0

        # ---- применяем бонусы сочетаний (combinations) перед вставкой в discipline_days ----
        try:
            # Используем row_factory, чтобы удобнее обращаться по именам
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Получаем список выполненных привычек за этот день (success = 1)
            cursor.execute('SELECT DISTINCT habit_id FROM completed_habits WHERE date = ? AND success = 1', (day_date,))
            done_rows = cursor.fetchall()
            done_ids = set([r['habit_id'] for r in done_rows]) if done_rows else set()

            if done_ids:
                # Берём все активные сочетания
                cursor.execute('SELECT * FROM combinations WHERE is_active = 1')
                combos = cursor.fetchall() or []
                for c in combos:
                    # Убедимся, что habit_a и habit_b в виде чисел и присутствуют
                    try:
                        ha = int(c['habit_a'])
                        hb = int(c['habit_b'])
                    except Exception:
                        continue
                    if ha in done_ids and hb in done_ids:
                        # Добавляем бонусы (если поле NULL -> 0.0)
                        totals['I'] += float(c.get('i') or 0.0)
                        totals['S'] += float(c.get('s') or 0.0)
                        totals['W'] += float(c.get('w') or 0.0)
                        totals['E'] += float(c.get('e') or 0.0)
                        totals['C'] += float(c.get('c') or 0.0)
                        totals['H'] += float(c.get('h') or 0.0)
                        totals['ST'] += float(c.get('st') or 0.0)
                        totals['$'] += float(c.get('money') or 0.0)
        except Exception as ex:
            # Не критично: логируем, но не мешаем основной операции
            print('Warning: error applying combinations bonuses:', ex)
        finally:
            # Вернём нормальный cursor (без row_factory) для дальнейших операций
            conn.row_factory = None
            cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO discipline_days 
            (date, day_number, state, emotion_morning, thoughts,
             total_i, total_s, total_w, total_e, total_c, total_h, total_st, total_money,
             completed_count, total_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            day_date,
            data.get('day_number'),
            data.get('state'),
            data.get('emotion_morning'),
            data.get('thoughts'),
            totals.get('I', 0.0),
            totals.get('S', 0.0),
            totals.get('W', 0.0),
            totals.get('E', 0.0),
            totals.get('C', 0.0),
            totals.get('H', 0.0),
            totals.get('ST', 0.0),
            totals.get('$', 0.0),
            data.get('completed_count', 0),
            data.get('total_count', 0)
        ))

        # Теперь фиксируем — коммитим изменения completed_habits и discipline_days
        conn.commit()

        # И — ключевая часть — пересчитываем все стрики по истории (на этом же соединении)
        recalc_all_streaks(conn)

        conn.close()

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/completions/<date>', methods=['GET'])
def get_completions(date):
    """Получение выполненных привычек за день"""
    try:
        conn = sqlite3.connect('habits.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Получаем привычки за день
        cursor.execute('''
            SELECT ch.*, h.name as habit_name, h.category, h.is_composite
            FROM completed_habits ch
            JOIN habits h ON ch.habit_id = h.id
            WHERE ch.date = ?
            ORDER BY h.category, h.name
        ''', (date,))
        
        habits = [dict(row) for row in cursor.fetchall()]
        
        # Получаем статистику дня
        cursor.execute('SELECT * FROM discipline_days WHERE date = ?', (date,))
        day_data = cursor.fetchone()
        
        # Получаем информацию о стриках
        streaks = {}
        for habit in habits:
            cursor.execute('SELECT current_streak, longest_streak FROM streaks WHERE habit_id = ?', 
                          (habit['habit_id'],))
            streak_data = cursor.fetchone()
            if streak_data:
                streaks[habit['habit_id']] = {
                    'current': streak_data[0],
                    'longest': streak_data[1]
                }
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'habits': habits,
            'day_data': dict(day_data) if day_data else None,
            'streaks': streaks
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============ API для статистики ============

@app.route('/api/stats/period', methods=['GET'])
def get_period_stats():
    """Получение статистики за период"""
    try:
        period = request.args.get('period', 'week')  # week, month, all
        end_date = date.today()
        
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        if period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date - timedelta(days=30)
        else:  # all
            cursor.execute('SELECT MIN(date) FROM discipline_days')
            min_date = cursor.fetchone()[0]
            start_date = datetime.strptime(min_date, '%Y-%m-%d').date() if min_date else end_date
        
        # Явные суммы и средние — чтобы фронт имел predictable ключи (sum_* и avg_*)
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT date) as days_count,
                SUM(total_i) as sum_i,
                SUM(total_s) as sum_s,
                SUM(total_w) as sum_w,
                SUM(total_e) as sum_e,
                SUM(total_c) as sum_c,
                SUM(total_h) as sum_h,
                SUM(total_st) as sum_st,
                SUM(total_money) as sum_money,
                AVG(total_i) as avg_i,
                AVG(total_s) as avg_s,
                AVG(total_w) as avg_w,
                AVG(total_e) as avg_e,
                AVG(total_c) as avg_c,
                AVG(total_h) as avg_h,
                AVG(total_st) as avg_st,
                AVG(total_money) as avg_money
            FROM discipline_days
            WHERE date BETWEEN ? AND ?
        ''', (start_date.isoformat(), end_date.isoformat()))

        row = cursor.fetchone() or (0,)+ (0,)*15  # безопасная подстраховка
        # row -> tuple in order of select
        cols = [c[0] for c in cursor.description]
        raw = dict(zip(cols, row))

        # нормализуем числа: None -> 0, строки -> float
        def _num(x):
            try:
                return float(x) if x is not None else 0.0
            except Exception:
                return 0.0

        stats = {
            'days_count': int(raw.get('days_count') or 0),
            'sum_i': _num(raw.get('sum_i')),
            'sum_s': _num(raw.get('sum_s')),
            'sum_w': _num(raw.get('sum_w')),
            'sum_e': _num(raw.get('sum_e')),
            'sum_c': _num(raw.get('sum_c')),
            'sum_h': _num(raw.get('sum_h')),
            'sum_st': _num(raw.get('sum_st')),
            'sum_money': _num(raw.get('sum_money')),
            'avg_i': _num(raw.get('avg_i')),
            'avg_s': _num(raw.get('avg_s')),
            'avg_w': _num(raw.get('avg_w')),
            'avg_e': _num(raw.get('avg_e')),
            'avg_c': _num(raw.get('avg_c')),
            'avg_h': _num(raw.get('avg_h')),
            'avg_st': _num(raw.get('avg_st')),
            'avg_money': _num(raw.get('avg_money')),
        }

        
        # Статистика по дням для графика
        cursor.execute('''
            SELECT date, total_i, total_s, total_w, total_e, total_c, total_h
            FROM discipline_days 
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        ''', (start_date.isoformat(), end_date.isoformat()))
        
        days_data = []
        for row in cursor.fetchall():
            days_data.append({
                'date': row[0],
                'I': row[1] or 0,
                'S': row[2] or 0,
                'W': row[3] or 0,
                'E': row[4] or 0,
                'C': row[5] or 0,
                'H': row[6] or 0
            })
        
        # Сравнение с предыдущим периодом
        if period == 'week':
            prev_start = start_date - timedelta(days=7)
            prev_end = start_date - timedelta(days=1)
        elif period == 'month':
            prev_start = start_date - timedelta(days=30)
            prev_end = start_date - timedelta(days=1)
        else:
            prev_start = start_date
            prev_end = end_date
        
        cursor.execute('''
            SELECT 
                AVG(total_i) as avg_i,
                AVG(total_s) as avg_s,
                AVG(total_w) as avg_w,
                AVG(total_e) as avg_e,
                AVG(total_c) as avg_c,
                AVG(total_h) as avg_h
            FROM discipline_days 
            WHERE date BETWEEN ? AND ?
        ''', (prev_start.isoformat(), prev_end.isoformat()))
        
        prev_stats = cursor.fetchone()
        
        comparison = {}
        if prev_stats:
            current_avgs = [stats['avg_i'], stats['avg_s'], stats['avg_w'], 
                           stats['avg_e'], stats['avg_c'], stats['avg_h']]
            prev_avgs = [prev_stats[0] or 0, prev_stats[1] or 0, prev_stats[2] or 0,
                        prev_stats[3] or 0, prev_stats[4] or 0, prev_stats[5] or 0]
            
            for i, stat_name in enumerate(['I', 'S', 'W', 'E', 'C', 'H']):
                current = current_avgs[i]
                previous = prev_avgs[i]
                if previous == 0:
                    comparison[stat_name] = '→'
                else:
                    change = ((current - previous) / abs(previous)) * 100
                    if change > 5:
                        comparison[stat_name] = '↑'
                    elif change < -5:
                        comparison[stat_name] = '↓'
                    else:
                        comparison[stat_name] = '→'
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'stats': stats,
            'days_data': days_data,
            'comparison': comparison
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def recalc_all_streaks(conn):
    """
    Пересчитать стрики для всех активных привычек по истории completed_habits.
    Использует переданное соединение (чтобы избежать проблем с несозревшими транзакциями).
    """
    cursor = conn.cursor()

    # Получаем все активные привычки
    cursor.execute('SELECT id FROM habits WHERE is_active = 1')
    habit_rows = cursor.fetchall()

    for (habit_id,) in habit_rows:
        # берем уникальные даты, где была success=1
        cursor.execute('''
            SELECT DISTINCT date FROM completed_habits
            WHERE habit_id = ? AND success = 1
            ORDER BY date
        ''', (habit_id,))
        date_rows = [row[0] for row in cursor.fetchall()]

        if not date_rows:
            # нет выполнений — сохраняем нулевой стрик
            cursor.execute('''
                INSERT OR REPLACE INTO streaks (habit_id, current_streak, longest_streak, last_date)
                VALUES (?, ?, ?, ?)
            ''', (habit_id, 0, 0, None))
            continue

        # парсим строки дат в объекты date
        parsed_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in date_rows]

        # посчитаем longest по всем сериями подряд
        longest = 1
        current_run = 1
        for i in range(1, len(parsed_dates)):
            if (parsed_dates[i] - parsed_dates[i-1]).days == 1:
                current_run += 1
            else:
                if current_run > longest:
                    longest = current_run
                current_run = 1
        if current_run > longest:
            longest = current_run

        # current_streak = длина серии, в которую входит самая последняя дата
        last_run_length = 1
        for i in range(len(parsed_dates)-1, 0, -1):
            if (parsed_dates[i] - parsed_dates[i-1]).days == 1:
                last_run_length += 1
            else:
                break

        last_date_str = parsed_dates[-1].isoformat()
        cursor.execute('''
            INSERT OR REPLACE INTO streaks (habit_id, current_streak, longest_streak, last_date)
            VALUES (?, ?, ?, ?)
        ''', (habit_id, last_run_length, longest, last_date_str))

    # один commit в конце — атомарно
    conn.commit()


@app.route('/api/stats/streaks', methods=['GET'])
def get_streaks():
    """Получение стриков привычек (включая нулевые)"""
    try:
        conn = sqlite3.connect('habits.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                h.id as habit_id,
                h.name,
                h.category,
                COALESCE(s.current_streak, 0) as current_streak,
                COALESCE(s.longest_streak, 0) as longest_streak,
                s.last_date
            FROM habits h
            LEFT JOIN streaks s ON h.id = s.habit_id
            WHERE h.is_active = 1
            ORDER BY current_streak DESC, longest_streak DESC, h.category, h.name
        ''')

        streaks = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify({'status': 'success', 'data': streaks})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/stats/total_days', methods=['GET'])
def get_total_days():
    """Получение общего количества дней дисциплины"""
    try:
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT date) FROM discipline_days')
        total_days = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT MAX(day_number) FROM discipline_days')
        max_day = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'total_days': total_days,
            'max_day': max_day
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats/daily_comparison', methods=['GET'])
def get_daily_comparison():
    """Сравнение характеристик с предыдущим днем"""
    try:
        target_date = request.args.get('date', date.today().isoformat())
        
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        
        # Получаем статистику за целевой день
        cursor.execute('''
            SELECT total_i, total_s, total_w, total_e, total_c, total_h, total_st, total_money
            FROM discipline_days WHERE date = ?
        ''', (target_date,))
        
        today_stats = cursor.fetchone()
        
        if not today_stats:
            return jsonify({'status': 'success', 'comparison': {}})
        
        # Получаем предыдущий день с данными
        cursor.execute('''
            SELECT date, total_i, total_s, total_w, total_e, total_c, total_h, total_st, total_money
            FROM discipline_days 
            WHERE date < ? 
            ORDER BY date DESC 
            LIMIT 1
        ''', (target_date,))
        
        prev_day = cursor.fetchone()
        
        comparison = {}
        if prev_day:
            stat_names = ['I', 'S', 'W', 'E', 'C', 'H', 'ST', '$']
            today_values = today_stats
            prev_values = prev_day[1:]
            
            for i, stat in enumerate(stat_names):
                today_val = today_values[i] or 0
                prev_val = prev_values[i] or 0
                
                if prev_val == 0:
                    if today_val > 0:
                        comparison[stat] = '↑'
                    elif today_val < 0:
                        comparison[stat] = '↓'
                    else:
                        comparison[stat] = '→'
                else:
                    change = ((today_val - prev_val) / abs(prev_val)) * 100
                    if change > 5:
                        comparison[stat] = '↑'
                    elif change < -5:
                        comparison[stat] = '↓'
                    else:
                        comparison[stat] = '→'
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'comparison': comparison,
            'prev_date': prev_day[0] if prev_day else None
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============ API для работы с файлами ============

@app.route('/api/save', methods=['POST'])
def save_data():
    """Сохранение данных в файл (для обратной совместимости)"""
    try:
        data = request.json
        
        if not os.path.exists('data'):
            os.makedirs('data')
        
        filename = f"data/report_{date.today().isoformat()}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'status': 'success', 
            'message': f'Данные сохранены в {filename}',
            'file': filename
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def export_data():
    """Экспорт данных в формате TXT или CSV"""
    try:
        data = request.json
        content = data.get('content', '')
        format_type = data.get('format', 'txt')
        
        if format_type == 'csv':
            return jsonify({
                'status': 'success',
                'content': content,
                'filename': f'report_{date.today()}.csv'
            })
        else:
            return jsonify({
                'status': 'success',
                'content': content,
                'filename': f'report_{date.today()}.txt'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============ Дополнительные эндпоинты ============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера и БД"""
    try:
        conn = sqlite3.connect('habits.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM habits')
        habits_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'habits_count': habits_count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Генератор отчетов дисциплины с БАЗОЙ ДАННЫХ")
    print("=" * 80)
    print("📍 Локальный сервер запущен по адресу: http://127.0.0.1:5000")
    print("")
    print("📊 ВОЗМОЖНОСТИ:")
    print("   • Полная интеграция с SQLite базой данных")
    print("   • Справочник привычек с характеристиками")
    print("   • Автоматический расчет стриков")
    print("   • Статистика за день/неделю/месяц/все время")
    print("   • Сравнение с предыдущими днями (стрелочки)")
    print("   • Счетчик дней дисциплины")
    print("")
    print("📡 ОСНОВНЫЕ API-ЭНДПОИНТЫ:")
    print("   GET  /api/habits          - справочник привычек")
    print("   POST /api/habits          - добавить привычку")
    print("   POST /api/completions     - сохранить выполнение")
    print("   GET  /api/stats/period    - статистика за период")
    print("   GET  /api/stats/streaks   - стрики привычек")
    print("   GET  /api/stats/total_days- общее количество дней")
    print("=" * 80)
    
    # Запускаем сервер
    app.run(debug=True, host='127.0.0.1', port=5000)