import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import datetime
import cv2
from pyzbar.pyzbar import decode
from PIL import Image, ImageTk
import csv

# DB接続と初期化
conn = sqlite3.connect('Column_History.db')
cursor = conn.cursor()

# テーブル初期化
cursor.execute('''
CREATE TABLE IF NOT EXISTS columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer TEXT,
    model TEXT,
    serial_number TEXT,
    purchase_date TEXT,
    qr_code_content TEXT UNIQUE
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_id INTEGER,
    date TEXT,
    user TEXT,
    compound TEXT,
    result TEXT,
    FOREIGN KEY (column_id) REFERENCES columns(id)
)
''')
conn.commit()

# 使用者・化合物候補
users = ["栗原", "小川", "念垣"]
cursor.execute("SELECT DISTINCT compound FROM usage_history")
compounds = [row[0] for row in cursor.fetchall()] + ["新規入力..."]

selected_column_id = None

# メインウィンドウ
root = tk.Tk()
root.title("HPLCカラム管理アプリ")
root.geometry("900x600")

# Notebook（タブ）
notebook = ttk.Notebook(root)
notebook.pack(expand=True, fill='both', padx=10, pady=10)

# 各タブフレーム
tab_register_usage = tk.Frame(notebook)
tab_column_register = tk.Frame(notebook)
tab_view_history = tk.Frame(notebook)
notebook.add(tab_register_usage, text="使用履歴登録")
notebook.add(tab_column_register, text="カラム登録")
notebook.add(tab_view_history, text="履歴表示")

# 共通関数
def simple_input(prompt):
    def ok():
        nonlocal value
        value = entry.get()
        dialog.destroy()

    value = None
    dialog = tk.Toplevel(root)
    dialog.title("新規入力")
    tk.Label(dialog, text=prompt).pack(padx=10, pady=5)
    entry = tk.Entry(dialog)
    entry.pack(padx=10, pady=5)
    tk.Button(dialog, text="OK", command=ok).pack(pady=5)
    dialog.grab_set()
    root.wait_window(dialog)
    return value

def scan_qr_code():
    cap = cv2.VideoCapture(0)
    result = None
    qr_img = None
    while True:
        ret, frame = cap.read()
        for barcode in decode(frame):
            result = barcode.data.decode('utf-8')
            (x, y, w, h) = barcode.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, result, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            qr_img = frame[y:y+h, x:x+w]
            break
        cv2.imshow('QRスキャン中（Escでキャンセル）', frame)
        if result or cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    return result, qr_img

def load_columns():
    cursor.execute("SELECT id, manufacturer || ' / ' || model FROM columns")
    return cursor.fetchall()

def select_column_from_list():
    global selected_column_id
    selection = combo_column_list.get()
    cursor.execute("SELECT id FROM columns WHERE manufacturer || ' / ' || model = ?", (selection,))
    result = cursor.fetchone()
    if result:
        selected_column_id = result[0]
        label_column_info.config(text=selection)

def scan_and_select_column():
    global selected_column_id
    qr_data, _ = scan_qr_code()
    if qr_data:
        cursor.execute("SELECT id, manufacturer, model FROM columns WHERE qr_code_content = ?", (qr_data,))
        result = cursor.fetchone()
        if result:
            selected_column_id = result[0]
            label_column_info.config(text=f"{result[1]} / {result[2]}")
            combo_column_list.set(f"{result[1]} / {result[2]}")
        else:
            messagebox.showerror("エラー", f"カラムが見つかりませんでした: {qr_data}")
    else:
        messagebox.showwarning("キャンセル", "QRコードが読み取られませんでした")

def insert_usage_record():
    if selected_column_id is None:
        messagebox.showwarning("未選択", "カラムを選択してください")
        return

    date = entry_date.get()
    user = combo_user.get()
    compound = combo_compound.get()
    result = var_result.get()

    if user == "新規入力...":
        user = simple_input("新しい使用者を入力してください")
    if compound == "新規入力...":
        compound = simple_input("新しい化合物を入力してください")

    if not (date and user and compound):
        messagebox.showwarning("入力エラー", "すべての項目を入力してください")
        return

    cursor.execute(
        "INSERT INTO usage_history (column_id, date, user, compound, result) VALUES (?, ?, ?, ?, ?)",
        (selected_column_id, date, user, compound, result)
    )
    conn.commit()
    messagebox.showinfo("成功", "使用履歴を登録しました")

# 使用履歴登録タブUI
tk.Label(tab_register_usage, text="使用日").grid(row=0, column=0, pady=5, sticky='e')
entry_date = tk.Entry(tab_register_usage)
entry_date.insert(0, datetime.date.today().isoformat())
entry_date.grid(row=0, column=1, pady=5, sticky='w')

tk.Label(tab_register_usage, text="使用者").grid(row=1, column=0, pady=5, sticky='e')
combo_user = ttk.Combobox(tab_register_usage, values=users, state="readonly")
combo_user.grid(row=1, column=1, pady=5, sticky='w')

tk.Label(tab_register_usage, text="化合物").grid(row=2, column=0, pady=5, sticky='e')
frame_compound = tk.Frame(tab_register_usage)
frame_compound.grid(row=2, column=1, columnspan=2, sticky='w')
combo_compound = ttk.Combobox(frame_compound, values=compounds)
combo_compound.pack(side='left')
tk.Button(frame_compound, text="CSVから追加", command=lambda: import_compounds_from_csv()).pack(side='left', padx=5)

tk.Label(tab_register_usage, text="合成成否").grid(row=3, column=0, pady=5, sticky='e')
var_result = tk.StringVar(value="成功")
frame_radio = tk.Frame(tab_register_usage)
tk.Radiobutton(frame_radio, text="成功", variable=var_result, value="成功").pack(side="left")
tk.Radiobutton(frame_radio, text="失敗", variable=var_result, value="失敗").pack(side="left")
frame_radio.grid(row=3, column=1, pady=5, sticky='w')

tk.Label(tab_register_usage, text="対象カラム").grid(row=4, column=0, pady=5, sticky='e')
label_column_info = tk.Label(tab_register_usage, text="（未選択）")
label_column_info.grid(row=4, column=1, sticky='w')

combo_column_list = ttk.Combobox(tab_register_usage, values=[name for _, name in load_columns()], state="readonly")
combo_column_list.grid(row=5, column=1, sticky='w', pady=5)
tk.Button(tab_register_usage, text="リストから選択", command=select_column_from_list).grid(row=5, column=2, padx=5)
tk.Button(tab_register_usage, text="QRスキャン", command=scan_and_select_column).grid(row=4, column=2, padx=5)

tk.Button(tab_register_usage, text="登録", command=insert_usage_record).grid(row=6, column=0, columnspan=3, pady=20)

# カラム登録タブUI
tk.Label(tab_column_register, text="メーカー").grid(row=0, column=0, pady=5, sticky='e')
entry_manufacturer = tk.Entry(tab_column_register)
entry_manufacturer.grid(row=0, column=1, pady=5)

tk.Label(tab_column_register, text="型番").grid(row=1, column=0, pady=5, sticky='e')
entry_model = tk.Entry(tab_column_register)
entry_model.grid(row=1, column=1, pady=5)

tk.Label(tab_column_register, text="シリアル番号").grid(row=2, column=0, pady=5, sticky='e')
entry_serial = tk.Entry(tab_column_register)
entry_serial.grid(row=2, column=1, pady=5)

tk.Label(tab_column_register, text="購入日").grid(row=3, column=0, pady=5, sticky='e')
entry_purchase = tk.Entry(tab_column_register)
entry_purchase.insert(0, datetime.date.today().isoformat())
entry_purchase.grid(row=3, column=1, pady=5)

tk.Label(tab_column_register, text="QRコード内容").grid(row=4, column=0, pady=5, sticky='e')
entry_qr = tk.Entry(tab_column_register)
entry_qr.grid(row=4, column=1, pady=5)

def scan_qr_for_column_register():
    qr_data, _ = scan_qr_code()
    if qr_data:
        entry_qr.delete(0, tk.END)
        entry_qr.insert(0, qr_data)
    else:
        messagebox.showwarning("キャンセル", "QRコードが読み取られませんでした")

def register_column():
    mfr = entry_manufacturer.get()
    model = entry_model.get()
    serial = entry_serial.get()
    date = entry_purchase.get()
    qr = entry_qr.get()

    if not all([mfr, model, serial, qr]):
        messagebox.showwarning("入力エラー", "すべての必須項目を入力してください")
        return

    try:
        cursor.execute("""
            INSERT INTO columns (manufacturer, model, serial_number, purchase_date, qr_code_content)
            VALUES (?, ?, ?, ?, ?)
        """, (mfr, model, serial, date, qr))
        conn.commit()
        messagebox.showinfo("成功", "カラムを登録しました")
    except sqlite3.IntegrityError:
        messagebox.showerror("登録エラー", "同じQRコードがすでに存在します")

tk.Button(tab_column_register, text="QRコード読取", command=scan_qr_for_column_register).grid(row=4, column=2, padx=5, pady=5)
tk.Button(tab_column_register, text="登録", command=register_column).grid(row=5, column=0, columnspan=2, pady=10)

# 履歴表示タブ
history_tree = ttk.Treeview(tab_view_history, columns=("日付", "使用者", "化合物", "成否", "カラム"), show='headings')
for col in ("日付", "使用者", "化合物", "成否", "カラム"):
    history_tree.heading(col, text=col)
    history_tree.column("日付", width=60)
    history_tree.column("使用者", width=60)
    history_tree.column("成否", width=60)
    history_tree.column("化合物", width=150)
    history_tree.column("カラム", width=200)
history_tree.pack(fill='both', expand=True, padx=10, pady=10)

history_tree.bind('<Double-1>', lambda event: edit_tree_item(event))

def edit_tree_item(event):
    selected = history_tree.selection()
    if not selected:
        return
    item = selected[0]
    values = history_tree.item(item, 'values')
    # Treeviewの項目IDは usage_history テーブルのID
    record_id = int(item)
    top = tk.Toplevel(root)
    top.title("履歴編集")
    entries = []
    labels = ["日付", "使用者", "化合物", "成否"]
    for i, label in enumerate(labels):
        tk.Label(top, text=label).grid(row=i, column=0)
        entry = tk.Entry(top)
        entry.insert(0, values[i])
        entry.grid(row=i, column=1)
        entries.append(entry)
    # カラム情報を表示（編集不可）
    tk.Label(top, text="カラム").grid(row=len(labels), column=0)
    tk.Label(top, text=values[4]).grid(row=len(labels), column=1)
    def save():
        new_values = [e.get() for e in entries]
        cursor.execute("UPDATE usage_history SET date=?, user=?, compound=?, result=? WHERE id=?",
                       (new_values[0], new_values[1], new_values[2], new_values[3], record_id))
        conn.commit()
        history_tree.item(item, values=(new_values[0], new_values[1], new_values[2], new_values[3], values[4]))
        top.destroy()
    tk.Button(top, text="保存", command=save).grid(row=len(labels)+1, column=0, columnspan=2, pady=10)

def load_history():
    history_tree.delete(*history_tree.get_children())
    cursor.execute("""
        SELECT uh.id, uh.date, uh.user, uh.compound, uh.result, c.model
        FROM usage_history uh
        JOIN columns c ON uh.column_id = c.id
        ORDER BY uh.date DESC
    """)
    for row in cursor.fetchall():
        history_tree.insert('', 'end', iid=str(row[0]), values=row[1:])

def scan_qr_and_filter():
    qr_data, _ = scan_qr_code()
    if qr_data:
        cursor.execute("SELECT id FROM columns WHERE qr_code_content = ?", (qr_data,))
        result = cursor.fetchone()
        if result:
            column_id = result[0]
            filter_history_by_column_id(column_id)
        else:
            messagebox.showinfo("該当なし", "このQRコードに該当するカラムはありません。")

def select_column_from_history_list():
    column_name = combo_column_filter.get()
    cursor.execute("SELECT id FROM columns WHERE manufacturer || ' / ' || model = ?", (column_name,))
    result = cursor.fetchone()
    if result:
        column_id = result[0]
        filter_history_by_column_id(column_id)

def filter_history_by_column_id(column_id):
    history_tree.delete(*history_tree.get_children())
    cursor.execute("""
        SELECT uh.id, uh.date, uh.user, uh.compound, uh.result, c.model
        FROM usage_history uh
        JOIN columns c ON uh.column_id = c.id
        WHERE c.id = ?
        ORDER BY uh.date DESC
    """, (column_id,))
    for row in cursor.fetchall():
        history_tree.insert('', 'end', iid=str(row[0]), values=row[1:])

button_frame = tk.Frame(tab_view_history)
button_frame.pack(pady=5)
tk.Button(button_frame, text="すべて表示", command=load_history).pack(side="left", padx=5)
tk.Button(button_frame, text="QRコードで絞り込み", command=scan_qr_and_filter).pack(side="left", padx=5)
combo_column_filter = ttk.Combobox(button_frame, values=[name for _, name in load_columns()], state="readonly")
combo_column_filter.pack(side="left", padx=5)
tk.Button(button_frame, text="選択で絞り込み", command=select_column_from_history_list).pack(side="left", padx=5)

# CSVから化合物追加
def import_compounds_from_csv():
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return
    with open(file_path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if row:
                combo_compound['values'] = tuple(set(combo_compound['values']) | {row[0]})

root.mainloop()

