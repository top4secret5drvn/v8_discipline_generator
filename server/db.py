import os
import sqlite3
from datetime import datetime


def init_db(db_path: str = 'habits.db'):
    """Инициализация базы данных при первом запуске."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS streaks (
            habit_id INTEGER NOT NULL,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_date DATE,
            FOREIGN KEY (habit_id) REFERENCES habits (id)
        )
    ''')

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
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_streaks_habit ON streaks(habit_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_completed_date ON completed_habits(date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_completed_habit ON completed_habits(habit_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_habits_category ON habits(category)')

    conn.commit()
    conn.close()


def update_streak(habit_id, date_str, success, db_path: str = 'habits.db'):
    """Обновление/создание стрика для привычки."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT habit_id, current_streak, longest_streak, last_date FROM streaks WHERE habit_id = ?', (habit_id,))
        streak = cursor.fetchone()

        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        if not streak:
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
                cursor.execute('''
                    UPDATE streaks SET
                        current_streak = ? 
                    WHERE habit_id = ?
                ''', (0, habit_id))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating streak: {e}")


def recalc_all_streaks(db_path: str = 'habits.db'):
    """
    Пересчитать стрики для всех активных привычек по истории completed_habits.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM habits WHERE is_active = 1')
    habit_rows = cursor.fetchall()

    for (habit_id,) in habit_rows:
        cursor.execute('''
            SELECT DISTINCT date FROM completed_habits
            WHERE habit_id = ? AND success = 1
            ORDER BY date
        ''', (habit_id,))
        date_rows = [row[0] for row in cursor.fetchall()]

        if not date_rows:
            cursor.execute('''
                INSERT OR REPLACE INTO streaks (habit_id, current_streak, longest_streak, last_date)
                VALUES (?, ?, ?, ?)
            ''', (habit_id, 0, 0, None))
            continue

        parsed_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in date_rows]

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

    conn.commit()
    conn.close()
