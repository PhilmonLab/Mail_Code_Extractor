import tkinter as tk
from tkinter import ttk
import requests
import time
import re
import threading

BASE_URL = "https://api.guerrillamail.com/ajax.php"

def get_temp_email():
    try:
        r = requests.get(BASE_URL, params={"f": "get_email_address"}, timeout=10)
        data = r.json()
        return data["email_addr"], data["sid_token"]
    except Exception as e:
        return None, None

def wait_for_code(token, log_func, result_callback, timeout=120, stop_event=None):
    log_func("Waiting for verification email...\n")
    elapsed = 0
    found = False
    while elapsed < timeout and not found:
        if stop_event and stop_event.is_set():
            log_func("Search stopped by user.\n")
            return
        try:
            r = requests.get(BASE_URL, params={
                "f": "get_email_list",
                "offset": 0,
                "sid_token": token
            }, timeout=10)
            data = r.json()
            emails = data.get("list", [])
            for mail in emails:
                subject = mail.get("mail_subject", "").lower()
                mail_id = mail.get("mail_id")
                if any(kw in subject for kw in ["code", "verification", "confirm", "telegram", "discord", "google", "meta"]):
                    log_func(f"Found possible email: {mail.get('mail_subject')}\n")
                    r2 = requests.get(BASE_URL, params={
                        "f": "fetch_email",
                        "email_id": mail_id,
                        "sid_token": token
                    }, timeout=10)
                    body = r2.json().get("mail_body", "")
                    match = re.search(r"\b(\d{6})\b", body)
                    if match:
                        code = match.group(1)
                        log_func(f"→ Code extracted: {code}\n")
                        result_callback(code)
                        found = True
                        return
            if not found:
                log_func(f"→ No code yet... ({elapsed}s)\n")
        except Exception as e:
            log_func(f"Polling error: {e}\n")
        time.sleep(5)
        elapsed += 5
    if not found:
        log_func("Timed out – no code found.\n")
        result_callback(None)

# ────────────────────────────────────────────────
#               GUI Part
# ────────────────────────────────────────────────

class GuerrillaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Shikamaru Nara → (奈良シカマル,")
        self.root.geometry("680x560")
        
        # State management - START WITH RUN (True)
        self.is_running = True
        self.stop_event = threading.Event()
        
        # Theme colors inspired by the images
        self.theme_running = {
            "bg": "#0f1419",
            "frame_bg": "#1a1f2e",
            "label_bg": "#1e2430",
            "text_bg": "#0a0e14",
            "accent": "#00ffcc",
            "text": "#00ffcc",
            "border": "#00ffcc",
            "glow": "#00ffcc"
        }
        
        self.theme_stopped = {
            "bg": "#1a1625",
            "frame_bg": "#2a2438",
            "label_bg": "#251e35",
            "text_bg": "#120e1a",
            "accent": "#a855f7",
            "text": "#c4b5fd",
            "border": "#a855f7",
            "glow": "#a855f7"
        }
        
        self.current_theme = self.theme_running
        self.root.configure(bg=self.current_theme["bg"])

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Running.Horizontal.TProgressbar",
                        thickness=20,
                        troughcolor="#1e2430",
                        background="#00ffcc",
                        borderwidth=0)
        
        style.configure("Stopped.Horizontal.TProgressbar",
                        thickness=20,
                        troughcolor="#251e35",
                        background="#a855f7",
                        borderwidth=0)

        # ── Switch frame ──
        switch_frame = tk.Frame(root, bg=self.current_theme["bg"])
        switch_frame.pack(fill="x", padx=20, pady=(20,15))
        
        # Create canvas for switch with glow effect
        self.switch_canvas = tk.Canvas(switch_frame, width=140, height=60, 
                                       bg=self.current_theme["bg"], 
                                       highlightthickness=0)
        self.switch_canvas.pack()
        
        # Draw rounded switch
        self.draw_switch()
        self.switch_canvas.bind("<Button-1>", self.toggle_switch)

        # ── Top frame (Email) ──
        self.top_frame = tk.Frame(root, bg=self.current_theme["bg"])
        self.top_frame.pack(fill="x", padx=20, pady=(5,10))

        self.mail_title = tk.Label(self.top_frame, text="EMAIL ADDRESS", 
                                   bg=self.current_theme["bg"], 
                                   fg=self.current_theme["accent"],
                                   font=("Arial", 10, "bold"))
        self.mail_title.pack(anchor="w", pady=(0,5))

        # Email container with copy button
        email_container = tk.Frame(self.top_frame, bg=self.current_theme["label_bg"], 
                                  relief="solid", borderwidth=2, 
                                  highlightbackground=self.current_theme["border"],
                                  highlightthickness=2)
        email_container.pack(fill="x")

        self.email_var = tk.StringVar(value="Click RUN to generate email")
        self.email_label = tk.Label(email_container, textvariable=self.email_var, 
                                    bg=self.current_theme["label_bg"], 
                                    fg=self.current_theme["text"],
                                    font=("Consolas", 11), anchor="w", padx=12, pady=10)
        self.email_label.pack(side="left", fill="x", expand=True)

        # Copy button
        self.copy_btn = tk.Label(email_container, text="📋", 
                                bg=self.current_theme["label_bg"],
                                fg=self.current_theme["accent"],
                                font=("Arial", 16), cursor="hand2", padx=10)
        self.copy_btn.pack(side="right")
        self.copy_btn.bind("<Button-1>", self.copy_email)

        # ── Code display ──
        self.code_frame = tk.Frame(root, bg=self.current_theme["bg"])
        self.code_frame.pack(pady=15)

        self.code_title = tk.Label(self.code_frame, text="VERIFICATION CODE", 
                                   bg=self.current_theme["bg"], 
                                   fg=self.current_theme["accent"],
                                   font=("Arial", 10, "bold"))
        self.code_title.pack(pady=(0,8))

        # Code display with glow
        code_container = tk.Frame(self.code_frame, bg=self.current_theme["label_bg"],
                                 relief="solid", borderwidth=3,
                                 highlightbackground=self.current_theme["border"],
                                 highlightthickness=3)
        code_container.pack()

        self.code_var = tk.StringVar(value="------")
        self.code_label = tk.Label(code_container, textvariable=self.code_var, 
                                   bg=self.current_theme["label_bg"], 
                                   fg="#4a5568",
                                   font=("Consolas", 40, "bold"), 
                                   padx=40, pady=20)
        self.code_label.pack()

        # ── Progress ──
        progress_frame = tk.Frame(root, bg=self.current_theme["bg"])
        progress_frame.pack(fill="x", padx=20, pady=(5,15))
        
        self.progress = ttk.Progressbar(progress_frame,
                                        mode="indeterminate",
                                        length=640,
                                        style="Running.Horizontal.TProgressbar")
        self.progress.pack()

        # ── Log area ──
        self.log_frame = tk.Frame(root, bg=self.current_theme["bg"])
        self.log_frame.pack(fill="both", expand=True, padx=20, pady=(0,20))

        log_container = tk.Frame(self.log_frame, bg=self.current_theme["text_bg"],
                                relief="solid", borderwidth=2,
                                highlightbackground=self.current_theme["border"],
                                highlightthickness=2)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_container, height=10, 
                               bg=self.current_theme["text_bg"], 
                               fg=self.current_theme["text"], 
                               font=("Consolas", 9),
                               insertbackground=self.current_theme["accent"], 
                               relief="flat", padx=10, pady=10)
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=scrollbar.set)

    def draw_switch(self):
        self.switch_canvas.delete("all")
        
        if self.is_running:
            # RUN state - cyan/green
            bg_color = "#00ffcc"
            text_color = "#0a0e14"
            text = "RUN"
            circle_x = 100
        else:
            # STOP state - purple
            bg_color = "#a855f7"
            text_color = "#0a0e14"
            text = "STOP"
            circle_x = 40
        
        # Draw rounded rectangle (switch background)
        self.switch_canvas.create_oval(10, 10, 50, 50, fill=bg_color, outline=bg_color, width=0)
        self.switch_canvas.create_oval(90, 10, 130, 50, fill=bg_color, outline=bg_color, width=0)
        self.switch_canvas.create_rectangle(30, 10, 110, 50, fill=bg_color, outline=bg_color, width=0)
        
        # Draw circle (toggle)
        self.switch_canvas.create_oval(circle_x-15, 15, circle_x+15, 45, 
                                       fill="#ffffff", outline="#ffffff", width=0)
        
        # Draw text
        self.switch_canvas.create_text(70, 30, text=text, 
                                       fill=text_color, 
                                       font=("Arial", 12, "bold"))

    def copy_email(self, event=None):
        email = self.email_var.get()
        if email and email != "Click RUN to generate email" and email != "Creating email...":
            self.root.clipboard_clear()
            self.root.clipboard_append(email)
            self.log("✓ Email copied to clipboard!\n")

    def toggle_switch(self, event=None):
        if self.is_running:
            # Switch to STOP
            self.is_running = False
            self.stop_event.set()
            self.current_theme = self.theme_stopped
            self.progress.stop()
            self.progress.config(style="Stopped.Horizontal.TProgressbar")
            self.log("═══ STOPPED ═══\n")
        else:
            # Switch to RUN
            self.is_running = True
            self.stop_event.clear()
            self.current_theme = self.theme_running
            self.progress.config(style="Running.Horizontal.TProgressbar")
            self.start_thread()
        
        # Redraw switch and apply theme
        self.draw_switch()
        self.apply_theme()

    def apply_theme(self):
        self.root.configure(bg=self.current_theme["bg"])
        self.top_frame.configure(bg=self.current_theme["bg"])
        self.code_frame.configure(bg=self.current_theme["bg"])
        self.log_frame.configure(bg=self.current_theme["bg"])
        self.switch_canvas.configure(bg=self.current_theme["bg"])
        
        self.mail_title.configure(bg=self.current_theme["bg"], 
                                 fg=self.current_theme["accent"])
        self.email_label.configure(bg=self.current_theme["label_bg"], 
                                  fg=self.current_theme["text"])
        self.copy_btn.configure(bg=self.current_theme["label_bg"],
                               fg=self.current_theme["accent"])
        self.code_title.configure(bg=self.current_theme["bg"], 
                                 fg=self.current_theme["accent"])
        self.code_label.configure(bg=self.current_theme["label_bg"])
        self.log_text.configure(bg=self.current_theme["text_bg"], 
                               fg=self.current_theme["text"],
                               insertbackground=self.current_theme["accent"])

    def log(self, msg):
        self.log_text.insert(tk.END, msg)
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def set_code(self, code):
        if code:
            self.code_var.set(code)
            # Code received - bright glow
            if self.is_running:
                self.code_label.configure(fg="#00ffcc")
            else:
                self.code_label.configure(fg="#a855f7")
            self.progress.stop()
            self.log("╔═══════════════════════════╗\n")
            self.log("║  CODE RECEIVED! ✓         ║\n")
            self.log("╚═══════════════════════════╝\n")
        else:
            self.code_var.set("------")
            self.code_label.configure(fg="#ef4444")

    def start_thread(self):
        self.email_var.set("Creating email...")
        self.code_var.set("------")
        self.code_label.configure(fg="#4a5568")
        self.log_text.delete("1.0", tk.END)
        self.progress.start(10)
        thread = threading.Thread(target=self.run_process, daemon=True)
        thread.start()

    def run_process(self):
        email, token = get_temp_email()
        if not email:
            self.log("Error: Could not create temp email.\n")
            self.email_var.set("Error")
            self.progress.stop()
            return
        self.email_var.set(email)
        self.log(f"╔══ Email Generated ══╗\n")
        self.log(f"║ {email}\n")
        self.log(f"╚═════════════════════╝\n")
        self.log("→ Paste this email into signup form\n")
        self.log("→ Waiting for verification code...\n\n")
        wait_for_code(token, self.log, self.set_code, stop_event=self.stop_event)


if __name__ == "__main__":
    root = tk.Tk()
    app = GuerrillaGUI(root)
    root.mainloop()
