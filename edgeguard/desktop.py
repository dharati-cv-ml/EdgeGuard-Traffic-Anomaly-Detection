"""EdgeGuard offline Windows desktop analytics. No browser or server required."""
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from .core import FEATURES, load_csv, train, predict, score, metrics, save_model, load_model, export_predictions

BG = '#101827'
PANEL = '#1a273a'
TEXT = '#e6effa'
MUTED = '#a7bad0'
CYAN = '#47d8d1'
RED = '#ff947f'


def score_histogram(scores, bins=12):
    """Compute histogram counts for raw anomaly scores without third-party libraries."""
    if bins < 1:
        raise ValueError('bins must be positive')
    if not scores:
        return [], []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        hi = lo + 1
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = [0] * bins
    for val in scores:
        idx = min(bins - 1, int((val - lo) / (hi - lo) * bins))
        counts[idx] += 1
    return edges, counts


def feature_deviations(model, row):
    """Explanatory feature deviations (not causal explanations)."""
    if not model:
        return []
    values = []
    for feature in FEATURES:
        center = model['centers'][feature]
        scale = model['scales'][feature]
        deviation = abs(float(row[feature]) - center) / scale
        values.append((feature, deviation))
    return sorted(values, key=lambda entry: entry[1], reverse=True)


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('EdgeGuard | Offline Traffic Intelligence')
        self.geometry('1380x880')
        self.minsize(1040, 680)
        self.configure(bg=BG)
        self.rows = []
        self.predictions = []
        self.model = None
        self.view_rows = []
        self.filter_choice = tk.StringVar(value='All records')
        self.search_text = tk.StringVar()
        self.status = tk.StringVar(value='Ready — sample data loaded locally')
        self.details = tk.StringVar(value='Select a traffic record to see its input features and prediction.')
        self.counts = {}
        self._configure_style()
        self._build_ui()
        sample = Path(__file__).resolve().parent.parent / 'data' / 'sample.csv'
        if sample.exists():
            self._load_path(sample)
        self.after(160, self.redraw)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=TEXT, font=('Segoe UI', 10))
        style.configure('Title.TLabel', background=BG, foreground=CYAN, font=('Segoe UI Semibold', 24))
        style.configure('TButton', padding=(11, 8), font=('Segoe UI', 10))
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(18, 10), font=('Segoe UI Semibold', 10))
        style.configure('Treeview', background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=27, font=('Segoe UI', 9))
        style.configure('Treeview.Heading', font=('Segoe UI Semibold', 9))
        style.map('Treeview', background=[('selected', '#27777d')], foreground=[('selected', '#ffffff')])
        style.configure('TCombobox', padding=6)

    def _build_ui(self):
        title = ttk.Frame(self)
        title.pack(fill='x', padx=20, pady=(14, 6))
        ttk.Label(title, text='EDGEGUARD', style='Title.TLabel').pack(side='left')
        ttk.Label(title, text='   Offline network anomaly analytics  |  Python 3.14', foreground=MUTED).pack(side='left', pady=(11, 0))
        actions = ttk.Frame(self)
        actions.pack(fill='x', padx=20, pady=(6, 10))
        for label, command in [('Load CSV', self.load), ('Train Model', self.train_model), ('Open Model', self.open_model), ('Save Model', self.save_model_action), ('Analyze Traffic', self.analyze), ('Export Results', self.export)]:
            ttk.Button(actions, text=label, command=command).pack(side='left', padx=(0, 7))
        ttk.Label(self, textvariable=self.status, foreground=MUTED).pack(fill='x', padx=20, pady=(0, 8))
        cards = ttk.Frame(self)
        cards.pack(fill='x', padx=20, pady=(0, 10))
        for key, label in [('total', 'TOTAL REQUESTS'), ('normal', 'NORMAL'), ('review', 'FLAGGED FOR REVIEW'), ('precision', 'PRECISION (SYNTHETIC)'), ('recall', 'RECALL (SYNTHETIC)')]:
            frame = tk.Frame(cards, bg=PANEL, padx=15, pady=11, highlightbackground='#32435a', highlightthickness=1)
            frame.pack(side='left', fill='x', expand=True, padx=(0, 8))
            tk.Label(frame, text=label, bg=PANEL, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w')
            var = tk.StringVar(value='—')
            tk.Label(frame, textvariable=var, bg=PANEL, fg=TEXT, font=('Segoe UI Semibold', 21)).pack(anchor='w')
            self.counts[key] = var
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=8)
        overview = ttk.Frame(self.notebook)
        self.notebook.add(overview, text='Analytics Dashboard')
        self.notebook.add(ttk.Frame(self.notebook), text='Dataset Explorer')
        explorer = self.notebook.nametowidget(self.notebook.tabs()[1])
        self._build_overview(overview)
        self._build_explorer(explorer)
        ttk.Label(self, text='Synthetic research demonstration — flags are review suggestions, not proof of attacks. No network requests or localhost.', foreground=MUTED, font=('Segoe UI', 9)).pack(anchor='w', padx=20, pady=(0, 10))

    def _build_overview(self, parent):
        upper = ttk.Frame(parent)
        upper.pack(fill='both', expand=True, pady=(12, 10))
        self.hist_canvas = tk.Canvas(upper, bg=PANEL, highlightthickness=0, height=290)
        self.hist_canvas.pack(side='left', fill='both', expand=True, padx=(0, 8))
        self.decision_canvas = tk.Canvas(upper, bg=PANEL, highlightthickness=0, width=370, height=290)
        self.decision_canvas.pack(side='left', fill='both')
        self.hist_canvas.bind('<Configure>', lambda event: self.redraw())
        self.decision_canvas.bind('<Configure>', lambda event: self.redraw())
        lower = ttk.Frame(parent)
        lower.pack(fill='both', expand=True, pady=(0, 8))
        self.feature_canvas = tk.Canvas(lower, bg=PANEL, highlightthickness=0, height=235)
        self.feature_canvas.pack(fill='both', expand=True)
        self.feature_canvas.bind('<Configure>', lambda event: self.redraw())

    def _build_explorer(self, parent):
        controls = ttk.Frame(parent)
        controls.pack(fill='x', pady=(12, 8))
        ttk.Label(controls, text='Show:').pack(side='left', padx=(5, 7))
        filt = ttk.Combobox(controls, textvariable=self.filter_choice, state='readonly', values=['All records', 'Flagged only', 'Normal only'], width=18)
        filt.pack(side='left')
        filt.bind('<<ComboboxSelected>>', lambda event: self.populate())
        ttk.Label(controls, text='  Search ID:').pack(side='left', padx=6)
        entry = ttk.Entry(controls, textvariable=self.search_text, width=24)
        entry.pack(side='left')
        entry.bind('<KeyRelease>', lambda event: self.populate())
        columns = ('timestamp', 'client_id', 'requests_per_min', 'error_rate', 'avg_response_ms', 'bytes_out_kb', 'unique_paths', 'anomaly_score', 'prediction', 'label')
        region = ttk.Frame(parent)
        region.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(region, columns=columns, show='headings', selectmode='browse')
        for col in columns:
            self.tree.heading(col, text=col.replace('_', ' ').title())
            self.tree.column(col, width=150 if col in ('timestamp', 'client_id') else 125, minwidth=90, stretch=False, anchor='center')
        vbar = ttk.Scrollbar(region, orient='vertical', command=self.tree.yview)
        hbar = ttk.Scrollbar(region, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vbar.grid(row=0, column=1, sticky='ns')
        hbar.grid(row=1, column=0, sticky='ew')
        region.grid_rowconfigure(0, weight=1)
        region.grid_columnconfigure(0, weight=1)
        self.tree.tag_configure('review', background='#57353b', foreground='#ffffff')
        self.tree.bind('<<TreeviewSelect>>', self.show_selected)
        detail_frame = tk.Frame(parent, bg=PANEL, padx=14, pady=12)
        detail_frame.pack(fill='x', pady=(10, 8))
        tk.Label(detail_frame, text='SELECTED REQUEST — FEATURE DETAILS', bg=PANEL, fg=CYAN, anchor='w', font=('Segoe UI Semibold', 10)).pack(fill='x')
        tk.Label(detail_frame, textvariable=self.details, bg=PANEL, fg=TEXT, justify='left', anchor='w', wraplength=1050, font=('Consolas', 10)).pack(fill='x', pady=(8, 0))

    def _load_path(self, path):
        rows = load_csv(path)
        self.rows = rows
        self.predictions = []
        self.model = None
        self.status.set(f'Loaded {len(rows)} records from {Path(path).name}. Train a model, then analyze traffic.')
        self.populate()
        self.update_cards()
        self.redraw()

    def load(self):
        path = filedialog.askopenfilename(filetypes=[('CSV datasets', '*.csv')])
        if path:
            try:
                self._load_path(path)
            except Exception as exc:
                messagebox.showerror('Dataset error', str(exc))

    def train_model(self):
        try:
            self.model = train(self.rows)
            self.predictions = []
            self.status.set(f'Model trained on {len(self.rows)} records, threshold {self.model["threshold"]:.4f}. Click Analyze Traffic.')
            self.populate()
            self.update_cards()
            self.redraw()
        except Exception as exc:
            messagebox.showerror('Training error', str(exc))

    def open_model(self):
        path = filedialog.askopenfilename(filetypes=[('EdgeGuard JSON model', '*.json')])
        if path:
            try:
                self.model = load_model(path)
                self.predictions = []
                self.status.set(f'Loaded model: {Path(path).name}. Click Analyze Traffic.')
            except Exception as exc:
                messagebox.showerror('Model load error', str(exc))

    def save_model_action(self):
        if self.model is None:
            messagebox.showwarning('No model', 'Train or open a model first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON model', '*.json')])
        if path:
            save_model(self.model, path)
            self.status.set(f'Saved model to {path}')

    def analyze(self):
        if self.model is None:
            messagebox.showwarning('No model', 'Train or load a model first.')
            return
        try:
            self.predictions = predict(self.model, self.rows)
            stats = metrics(self.predictions)
            self.status.set(f'Analyzed {stats["count"]} requests; {stats["review_count"]} flagged. Scores are unbounded deviations, not probabilities.')
            self.populate()
            self.update_cards()
            self.redraw()
        except Exception as exc:
            messagebox.showerror('Analysis error', str(exc))

    def update_cards(self):
        total = len(self.rows)
        reviewed = sum(row['prediction'] == 'REVIEW' for row in self.predictions)
        stats = metrics(self.predictions) if self.predictions else {}
        for key, val in [('total', str(total)), ('normal', str(total - reviewed) if self.predictions else '—'), ('review', str(reviewed) if self.predictions else '—'), ('precision', f'{stats["precision"]:.1%}' if stats.get('precision') is not None else 'N/A'), ('recall', f'{stats["recall"]:.1%}' if stats.get('recall') is not None else 'N/A')]:
            self.counts[key].set(val)

    def populate(self):
        self.tree.delete(*self.tree.get_children())
        source = self.predictions if self.predictions else self.rows
        choice = self.filter_choice.get()
        search = self.search_text.get().lower().strip()
        self.view_rows = [row for row in source if (choice == 'All records' or row.get('prediction') == ('REVIEW' if choice == 'Flagged only' else 'NORMAL')) and search in str(row.get('client_id', '')).lower()]
        for i, row in enumerate(self.view_rows):
            values = [f'{row[col]:.4f}' if isinstance(row.get(col), float) else row.get(col, '') for col in self.tree['columns']]
            self.tree.insert('', 'end', iid=str(i), values=values, tags=('review',) if row.get('prediction') == 'REVIEW' else ())
        self.details.set(f'{len(self.view_rows)} matching records. Click a row for a detailed explanation.')

    def show_selected(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        row = self.view_rows[int(selected[0])]
        pairs = [f'{k}: {row[k]}' for k in FEATURES]
        lines = [f'Client: {row.get("client_id", "—")}  |  Timestamp: {row.get("timestamp", "—")}', '   '.join(pairs)]
        if self.model and 'anomaly_score' in row:
            lines.append(f'Score: {row["anomaly_score"]:.4f}  |  Threshold: {self.model["threshold"]:.4f}  |  Decision: {row["prediction"]}')
            top = feature_deviations(self.model, row)[:3]
            lines.append('Largest standardized deviations: ' + ', '.join(f'{name} ({value:.1f}x)' for name, value in top))
            lines.append('Feature deviations are diagnostic indicators, not proof of an attack.')
        self.details.set('\n'.join(lines))

    def redraw(self):
        if not hasattr(self, 'hist_canvas'):
            return
        self._draw_histogram()
        self._draw_decisions()
        self._draw_features()

    def _canvas_header(self, canvas, title, subtitle):
        canvas.delete('all')
        canvas.create_text(22, 22, text=title, fill=TEXT, anchor='w', font=('Segoe UI Semibold', 13))
        canvas.create_text(22, 44, text=subtitle, fill=MUTED, anchor='w', font=('Segoe UI', 9))

    def _draw_histogram(self):
        c = self.hist_canvas
        self._canvas_header(c, 'Anomaly score distribution', 'Actual model scores (not probabilities)')
        scores = [float(row['anomaly_score']) for row in self.predictions]
        if not scores:
            c.create_text(24, 115, anchor='w', text='Train and analyze traffic to display the score distribution.', fill=MUTED)
            return
        edges, counts = score_histogram(scores)
        w = max(c.winfo_width(), 500)
        h = max(c.winfo_height(), 240)
        left, top, bottom = 55, 83, h - 40
        usable = max(100, w - left - 30)
        max_count = max(counts) or 1
        for i, n in enumerate(counts):
            x0 = left + usable * i / len(counts) + 2
            x1 = left + usable * (i + 1) / len(counts) - 3
            y = bottom - (bottom - top) * n / max_count
            c.create_rectangle(x0, y, x1, bottom, fill=CYAN if i < 9 else RED, outline='')
            if n:
                c.create_text((x0+x1)/2, y-10, text=str(n), fill=TEXT, font=('Segoe UI', 8))
        c.create_text(left, bottom+17, text=f'{edges[0]:.2f}', fill=MUTED, anchor='w')
        c.create_text(left+usable, bottom+17, text=f'{edges[-1]:.2f}', fill=MUTED, anchor='e')
        threshold = self.model['threshold']
        if edges[-1] != edges[0]:
            tx = left + usable * min(1, max(0, (threshold - edges[0])/(edges[-1]-edges[0])))
            c.create_line(tx, top-10, tx, bottom, fill='#f7c56b', dash=(5, 4), width=2)
            c.create_text(min(w-70, max(90, tx)), top-20, text=f'threshold {threshold:.2f}', fill='#f7c56b', font=('Segoe UI', 8))

    def _draw_decisions(self):
        c = self.decision_canvas
        self._canvas_header(c, 'Inspection decisions', 'Review flags from the current dataset')
        if not self.predictions:
            c.create_text(22, 115, anchor='w', text='No predictions yet.', fill=MUTED)
            return
        normal = sum(r['prediction'] == 'NORMAL' for r in self.predictions)
        flagged = len(self.predictions) - normal
        total = max(1, len(self.predictions))
        w = max(c.winfo_width(), 300)
        x0, x1 = 25, w-25
        split = x0+(x1-x0)*normal/total
        c.create_rectangle(x0, 110, split, 158, fill=CYAN, outline='')
        c.create_rectangle(split, 110, x1, 158, fill=RED, outline='')
        c.create_text(25, 185, anchor='w', fill=TEXT, text=f'Normal: {normal} ({normal/total:.1%})', font=('Segoe UI', 11))
        c.create_text(25, 214, anchor='w', fill=TEXT, text=f'Review: {flagged} ({flagged/total:.1%})', font=('Segoe UI', 11))

    def _draw_features(self):
        c = self.feature_canvas
        self._canvas_header(c, 'Typical feature deviations of flagged records', 'Median standardized deviation per feature — descriptive, not causal')
        flagged = [r for r in self.predictions if r['prediction'] == 'REVIEW']
        if not flagged:
            c.create_text(22, 115, anchor='w', fill=MUTED, text='Analyze traffic to compare anomalous feature patterns.')
            return
        import statistics
        measurements = [(feature, statistics.median(abs(float(r[feature])-self.model['centers'][feature])/self.model['scales'][feature] for r in flagged)) for feature in FEATURES]
        maxval = max(x[1] for x in measurements) or 1
        width = max(c.winfo_width(), 500)
        right = width - 65
        for i, (name, val) in enumerate(measurements):
            y = 83 + i * 27
            c.create_text(18, y+7, text=name.replace('_', ' '), anchor='w', fill=TEXT, font=('Segoe UI', 9))
            start = 180
            end = start + max(1, right-start)*min(1, val/maxval)
            c.create_rectangle(start, y, end, y+15, fill=CYAN, outline='')
            c.create_text(min(width-35, end+8), y+7, text=f'{val:.1f}x', anchor='w', fill=TEXT, font=('Segoe UI', 9))

    def export(self):
        if not self.predictions:
            messagebox.showwarning('No results', 'Run Analyze Traffic first.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV result', '*.csv')])
        if path:
            try:
                export_predictions(self.predictions, path)
                messagebox.showinfo('Export complete', f'Saved {len(self.predictions)} rows to {path}')
            except Exception as exc:
                messagebox.showerror('Export error', str(exc))


def main():
    Dashboard().mainloop()


if __name__ == '__main__':
    main()
