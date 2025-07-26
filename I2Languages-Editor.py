import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
# To use the drag-and-drop feature, this library must be installed:
# pip install tkinterdnd2
import tkinterdnd2
import re

class I2Editor(tkinterdnd2.Tk):
    def __init__(self):
        super().__init__()
        
        # Main window settings
        self.title("I2Languages Editor By MrGamesKingPro")
        self.geometry("1100x700")

        self.data = None
        self.current_filepath = None
        self.term_to_tree_item = {} 
        self.term_to_original_index = {}
        self.terms_list_ref = None 
        
        # Variable to store the key of the term currently being edited
        self.currently_editing_term_key = None
        
        self.language_names = []
        self.detected_english_index = None

        # Create the user interface
        self._create_widgets()
        
        # Register the window as a drop target for files
        self.drop_target_register('DND_FILES')
        self.dnd_bind('<<Drop>>', self.on_drop)

    def _create_widgets(self):
        # --- Top Menu ---
        self.menu = tk.Menu(self)
        self.config(menu=self.menu)
        
        file_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open...", command=self.open_file_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Export to TXT...", command=self.export_to_txt)
        file_menu.add_command(label="Import from TXT...", command=self.import_from_txt)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # --- Top Toolbar Frame ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Select Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.language_var = tk.StringVar()
        self.language_combo = ttk.Combobox(top_frame, textvariable=self.language_var, 
                                           values=[], state="disabled")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        search_frame = ttk.Frame(top_frame, padding="10")
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Find:").grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(search_frame, text="Find Next", command=self.find_next).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(search_frame, text="Replace:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.replace_entry = ttk.Entry(search_frame)
        self.replace_entry.grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(search_frame, text="Replace", command=self.replace_selected).grid(row=1, column=2, padx=5, pady=2)
        ttk.Button(search_frame, text="Replace All", command=self.replace_all).grid(row=1, column=3, padx=5, pady=2)

        # Use a PanedWindow to split the interface
        # This allows the user to resize the table and editor sections
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        # --- Top Frame for the Treeview ---
        tree_frame = ttk.Frame(main_pane, padding=(0, 10, 0, 0))
        main_pane.add(tree_frame, weight=3) # Give the table more space by default
        
        columns = ("#", "term", "text")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("#", text="No.")
        self.tree.heading("term", text="Term Key")
        self.tree.heading("text", text="Translation Text (Preview)") # Text changed to indicate it's a preview
        
        self.tree.column("#", width=50, anchor='center')
        self.tree.column("term", width=300)
        self.tree.column("text", width=650)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        # Bind the treeview selection event
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Create the bottom editor panel
        editor_frame = ttk.LabelFrame(main_pane, text="Full Text Editor", padding="10")
        main_pane.add(editor_frame, weight=1) # Give the editor less space by default

        self.editor_text = tk.Text(editor_frame, wrap="word", height=10, width=80, undo=True)
        self.editor_text.pack(expand=True, fill="both", side="left", padx=(0, 10))
        self.editor_text.config(state="disabled") # Disable it until an item is selected

        editor_scrollbar = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=self.editor_text.yview)
        self.editor_text.configure(yscrollcommand=editor_scrollbar.set)
        editor_scrollbar.pack(side="left", fill="y")
        
        self.save_button = ttk.Button(editor_frame, text="Save Changes", command=self.save_from_editor, state="disabled")
        self.save_button.pack(pady=10, anchor="n")

        # --- Bottom Status Bar ---
        self.status_bar = ttk.Label(self, text="Open an I2Languages JSON file to begin, or drag & drop a file here.", relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Bind keyboard shortcuts
        self.bind("<Control-o>", lambda event: self.open_file_dialog())
        self.bind("<Control-s>", lambda event: self.save_file())
        self.bind("<Control-S>", lambda event: self.save_file_as())

    def on_tree_select(self, event):
        """
        When the user selects a row in the treeview, this function displays the full text
        in the text editor below.
        """
        selected_items = self.tree.selection()
        if not selected_items:
            # If nothing is selected, clear and disable the editor
            self.editor_text.config(state="normal")
            self.editor_text.delete("1.0", "end")
            self.editor_text.config(state="disabled")
            self.save_button.config(state="disabled")
            self.currently_editing_term_key = None
            return

        item_id = selected_items[0]
        item_values = self.tree.item(item_id, "values")
        term_key = item_values[1]
        
        # Get the full original text from the data, not from the treeview preview
        lang_index = self._get_selected_language_index()
        original_index = self.term_to_original_index.get(term_key)

        if lang_index is None or original_index is None:
            return # Something went wrong, do nothing

        try:
            full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]
        except (KeyError, IndexError):
            full_text = ""

        # Update the text editor
        self.editor_text.config(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", full_text)
        self.save_button.config(state="normal")
        self.currently_editing_term_key = term_key

    def save_from_editor(self):
        """
        Saves the text from the text editor into the data structure and updates the treeview.
        """
        if not self.currently_editing_term_key:
            return
        
        new_text = self.editor_text.get("1.0", "end-1c")
        self.update_data_and_tree(self.currently_editing_term_key, new_text)
        self.status_bar.config(text=f"Saved changes for term: {self.currently_editing_term_key}")


    def on_drop(self, event):
        try:
            # The path might be wrapped in curly braces, so we clean it
            filepath = self.tk.splitlist(event.data)[0]
            if filepath.startswith('{') and filepath.endswith('}'):
                filepath = filepath[1:-1]
            
            self.load_file_logic(filepath)
        except Exception as e:
            messagebox.showerror("Drag & Drop Error", f"Could not open the dropped file.\n\nError: {e}")
            self.status_bar.config(text="Drag & drop failed.")

    def open_file_dialog(self):
        filepath = filedialog.askopenfilename(
            title="Open I2Languages JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        self.load_file_logic(filepath)

    def load_file_logic(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # Find the 'Array' of terms, which can be in a few different places
            self.terms_list_ref = None
            if 'mSource' in self.data and isinstance(self.data.get('mSource'), dict) and 'mTerms' in self.data['mSource']:
                self.terms_list_ref = self.data['mSource']['mTerms'].get('Array')
            elif 'mTerms' in self.data and isinstance(self.data.get('mTerms'), dict):
                 self.terms_list_ref = self.data['mTerms'].get('Array')
            
            if self.terms_list_ref is None:
                raise ValueError("Invalid I2Languages file structure. Could not find 'mTerms' data.")

            self.current_filepath = filepath
            
            self.detect_languages()
            self.populate_treeview()
            self.title(f"I2Languages Editor By MrGamesKingPro - {filepath.split('/')[-1]}")
            self.status_bar.config(text=f"File loaded: {filepath}")

        except (json.JSONDecodeError, ValueError, KeyError, FileNotFoundError) as e:
            messagebox.showerror("Error", f"Failed to open or parse file: {e}\n\nPlease make sure it's a valid I2Languages JSON file.")
            self.data = None
            self.current_filepath = None
            self.terms_list_ref = None
            self.tree.delete(*self.tree.get_children())
            self.language_combo.config(state="disabled")
            self.language_combo.set('')

    def detect_languages(self):
        self.language_names = []
        self.detected_english_index = None

        if not self.terms_list_ref:
            self.status_bar.config(text="Warning: File contains no terms.")
            return

        # Assume all terms have the same number of languages
        num_languages = len(self.terms_list_ref[0].get('Languages', {}).get('Array', []))
        self.language_names = [f"Language {i+1}" for i in range(num_languages)]

        # Try to find English by looking for common, untranslated terms
        search_terms = {'Cancel': 'Cancel', 'RUN': 'RUN', '3DMark/RUN': 'RUN'}
        found_english = False
        for term_key, english_value in search_terms.items():
            for term_data in self.terms_list_ref:
                if term_data.get('Term') == term_key:
                    translations = term_data.get('Languages', {}).get('Array', [])
                    for j, text in enumerate(translations):
                        if text == english_value:
                            self.detected_english_index = j
                            found_english = True
                            break
                if found_english:
                    break
            if found_english:
                break
        
        self.language_combo.config(values=self.language_names, state="readonly")
        
        if self.detected_english_index is not None:
            self.language_var.set(self.language_names[self.detected_english_index])
            self.status_bar.config(text=f"Detected {num_languages} languages. English (Language {self.detected_english_index + 1}) set as default.")
        elif self.language_names:
            self.language_var.set(self.language_names[0])
            self.status_bar.config(text=f"Detected {num_languages} languages. English not found, defaulting to Language 1.")
        else:
             self.language_combo.config(state="disabled")

    def _get_selected_language_index(self):
        selected_lang_str = self.language_var.get()
        if not selected_lang_str:
            return None
        try:
            # e.g., "Language 5" -> 4
            return int(selected_lang_str.split(' ')[1]) - 1
        except (IndexError, ValueError):
            return None

    def populate_treeview(self):
        if not self.data or not self.terms_list_ref: return
        self.tree.delete(*self.tree.get_children())
        self.term_to_tree_item.clear()
        self.term_to_original_index.clear()
        
        # Clear and disable the editor when reloading the table
        self.on_tree_select(None)
        
        lang_index = self._get_selected_language_index()
        if lang_index is None:
            self.status_bar.config(text="Error: No language selected or invalid format.")
            return

        for i, term_data in enumerate(self.terms_list_ref, 1):
            term_key = term_data.get('Term', '[NO TERM KEY]')
            try:
                full_translation = term_data.get('Languages', {}).get('Array', [])[lang_index]
            except IndexError:
                full_translation = "[NO TEXT FOR THIS LANGUAGE]"
            
            # Clean up the text for display in the treeview
            # Replace newlines with spaces to keep it on a single line
            display_translation = full_translation.replace('\n', ' ').replace('\r', ' ').strip()
            
            item_id = self.tree.insert("", "end", values=(i, term_key, display_translation))
            self.term_to_tree_item[term_key] = item_id
            self.term_to_original_index[term_key] = i - 1

    def on_language_change(self, event=None):
        self.populate_treeview()
        self.status_bar.config(text=f"Displaying language: {self.language_var.get()}")

    def update_data_and_tree(self, term_key, new_text):
        if not self.data or not self.terms_list_ref: return
        
        lang_index = self._get_selected_language_index()
        if lang_index is None: return

        original_index = self.term_to_original_index[term_key]
        
        # Ensure the language array is long enough
        lang_array = self.terms_list_ref[original_index]['Languages']['Array']
        while len(lang_array) <= lang_index:
            lang_array.append("")

        # Update the data in memory
        lang_array[lang_index] = new_text

        # Update the preview value in the treeview as well
        item_id = self.term_to_tree_item[term_key]
        current_values = self.tree.item(item_id, "values")
        row_number = current_values[0]
        # Clean the new text for preview display
        display_text = new_text.replace('\n', ' ').replace('\r', ' ').strip()
        self.tree.item(item_id, values=(row_number, term_key, display_text))
        
        self.status_bar.config(text=f"Updated term: {term_key}")

    def save_file(self):
        if not self.current_filepath:
            self.save_file_as()
        else:
            self._write_to_file(self.current_filepath)

    def save_file_as(self):
        initial_filename = "I2Languages-resources.json"
        if self.current_filepath:
            initial_filename = self.current_filepath.split('/')[-1]

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=initial_filename
        )
        if not filepath: return
        self.current_filepath = filepath
        self._write_to_file(filepath)
        self.title(f"I2Languages Editor By MrGamesKingPro - {filepath.split('/')[-1]}")

    def _write_to_file(self, filepath):
        if not self.data:
            messagebox.showwarning("No Data", "There is no data to save.")
            return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            self.status_bar.config(text=f"File saved successfully: {filepath}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file: {e}")
            self.status_bar.config(text=f"Error saving file: {e}")

    def export_to_txt(self):
        if not self.data:
            messagebox.showwarning("No Data", "Please open a file first before exporting.")
            return
        filepath = filedialog.asksaveasfilename(
            title="Export translations to TXT", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Export the full text from the original data
                lang_index = self._get_selected_language_index()
                if lang_index is None: return

                for item_id in self.tree.get_children():
                    term_key = self.tree.item(item_id, "values")[1]
                    original_index = self.term_to_original_index[term_key]
                    full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]
                    f.write(full_text + '\n')

            self.status_bar.config(text=f"Successfully exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export file: {e}")
    
    def import_from_txt(self):
        if not self.data:
            messagebox.showwarning("No Data", "Please open a file first before importing.")
            return
        filepath = filedialog.askopenfilename(
            title="Import translations from TXT", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            tree_items = self.tree.get_children()
            if len(lines) != len(tree_items):
                msg = (f"The number of lines in the text file ({len(lines)}) does not match "
                       f"the number of terms in the table ({len(tree_items)}).\n\n"
                       "Do you want to proceed and import matching lines only?")
                if not messagebox.askyesno("Line Count Mismatch", msg): return
            
            count = 0
            for item_id, new_line in zip(tree_items, lines):
                term_key = self.tree.item(item_id, "values")[1]
                # Text from file might contain trailing newlines, so we strip them
                new_text = new_line.rstrip('\n\r')
                self.update_data_and_tree(term_key, new_text)
                count += 1
            
            # Refresh the editor if an item is currently selected
            self.on_tree_select(None) # Clear it first
            selected = self.tree.selection()
            if selected:
                self.tree.event_generate("<<TreeviewSelect>>") # Re-trigger selection event

            self.status_bar.config(text=f"Successfully imported {count} lines from {filepath}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not import file: {e}")

    def find_next(self):
        query = self.search_entry.get()
        if not query: return
        
        all_items = self.tree.get_children()
        if not all_items: return

        # Start search from the item after the currently selected one
        selected_item = self.tree.focus()
        start_index = 0
        if selected_item:
            try:
                start_index = self.tree.index(selected_item) + 1
            except ValueError: # Should not happen if item is focused
                start_index = 0

        # Create a re-ordered list to search from start_index to end, then wrap around
        items_to_search = all_items[start_index:] + all_items[:start_index]

        lang_index = self._get_selected_language_index()
        if lang_index is None: return

        for item in items_to_search:
            # Search in the full text, not just the preview
            term_key = self.tree.item(item, "values")[1]
            original_index = self.term_to_original_index[term_key]
            full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]

            if query.lower() in full_text.lower():
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item) # Scroll to the item
                self.status_bar.config(text=f"Found '{query}'")
                return
        
        self.status_bar.config(text=f"No more occurrences of '{query}' found.")
        messagebox.showinfo("Search Finished", f"No more occurrences of '{query}' were found.")

    def replace_selected(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showinfo("Info", "Please select a row to replace.")
            return

        # Replacement now happens directly in the text editor widget
        query = self.search_entry.get()
        replace_with = self.replace_entry.get()
        if not query or self.editor_text.cget("state") == "disabled":
            messagebox.showinfo("Info", "Please select a row and enter a search term.")
            return

        # Replace only the first occurrence in the editor's current text
        current_text = self.editor_text.get("1.0", "end-1c")
        new_text, count = re.subn(re.escape(query), replace_with, current_text, count=1, flags=re.IGNORECASE)
        
        if count > 0:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", new_text)
            self.status_bar.config(text="Replaced text in editor. Click 'Save Changes' to commit.")
        else:
            self.status_bar.config(text="Search text not found in the editor for the selected row.")

    def replace_all(self):
        query = self.search_entry.get()
        replace_with = self.replace_entry.get()
        if not query:
            messagebox.showinfo("Info", "Please enter a search term in the 'Find' box.")
            return
            
        if not messagebox.askyesno("Confirm Replace All", f"Are you sure you want to replace all occurrences of '{query}' with '{replace_with}'? This cannot be undone."):
            return

        count = 0
        lang_index = self._get_selected_language_index()
        if lang_index is None: return

        for item_id in self.tree.get_children():
            values = self.tree.item(item_id, "values")
            term_key = values[1]
            
            # Get the full text, perform the replacement, then update
            original_index = self.term_to_original_index[term_key]
            old_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]

            new_text, num_replacements = re.subn(re.escape(query), replace_with, old_text, flags=re.IGNORECASE)

            if num_replacements > 0:
                self.update_data_and_tree(term_key, new_text)
                count += num_replacements
        
        # Refresh the editor if the currently edited item was changed
        if self.currently_editing_term_key:
            self.tree.event_generate("<<TreeviewSelect>>")

        self.status_bar.config(text=f"Replaced {count} occurrence(s) in total.")
        messagebox.showinfo("Replace All", f"Finished. Replaced {count} occurrence(s).")


if __name__ == "__main__":
    app = I2Editor()
    app.mainloop()
