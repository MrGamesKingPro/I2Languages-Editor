import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
# To use the drag-and-drop feature, this library must be installed:
# pip install tkinterdnd2
import tkinterdnd2
import re

# We inherit from tkinterdnd2.TkinterDnD.Tk for the most reliable drag-and-drop functionality.
class I2Editor(tkinterdnd2.TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        # --- Main window settings ---
        self.title("I2Languages Editor By MrGamesKingPro")
        self.geometry("1100x700")

        # --- Application state variables ---
        self.data = None  # Holds the entire loaded JSON data structure.
        self.current_filepath = None  # Stores the path to the currently open file.
        self.term_to_tree_item = {}  # A dictionary to quickly find a treeview item by its term key.
        self.term_to_original_index = {} # Maps a term key to its original index in the JSON array.
        self.terms_list_ref = None  # A direct reference to the list of terms in the loaded JSON.
        
        # Variable to store the key of the term currently being edited in the Text widget.
        self.currently_editing_term_key = None
        
        # List of language names detected from the file.
        self.language_names = []
        # The index of the language we guess is English, for user convenience.
        self.detected_english_index = None

        # --- Build the user interface ---
        self._create_widgets()
        
        # Register the main window as a drop target for files.
        # This allows the on_drop function to be called when a file is dropped onto the window.
        self.drop_target_register('DND_FILES')
        self.dnd_bind('<<Drop>>', self.on_drop)

    def _create_widgets(self):
        # --- Top Menu Bar ---
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
        
        # --- Top Toolbar Frame (for language selection and search) ---
        top_frame = ttk.Frame(self, padding="10")
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="Select Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.language_var = tk.StringVar()
        self.language_combo = ttk.Combobox(top_frame, textvariable=self.language_var, 
                                           values=[], state="disabled")
        self.language_combo.pack(side=tk.LEFT, padx=5)
        self.language_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        # --- Search and Replace Frame (aligned to the right) ---
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

        # Use a PanedWindow to create a resizable split between the table and the editor.
        main_pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_pane.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        # --- Top Frame for the Treeview (list of terms) ---
        tree_frame = ttk.Frame(main_pane, padding=(0, 10, 0, 0))
        main_pane.add(tree_frame, weight=3) # Give the table more space by default.
        
        columns = ("#", "term", "text")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        self.tree.heading("#", text="No.")
        self.tree.heading("term", text="Term Key")
        self.tree.heading("text", text="Translation Text (Preview)")
        
        self.tree.column("#", width=50, anchor='center')
        self.tree.column("term", width=300)
        self.tree.column("text", width=650)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        # Bind the selection event to update the text editor below.
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # --- Bottom Frame for the full text editor ---
        editor_frame = ttk.LabelFrame(main_pane, text="Full Text Editor", padding="10")
        main_pane.add(editor_frame, weight=1) # Give the editor less space by default.

        self.editor_text = tk.Text(editor_frame, wrap="word", height=10, width=80, undo=True)
        self.editor_text.pack(expand=True, fill="both", side="left", padx=(0, 10))
        self.editor_text.config(state="disabled") # Disable until an item is selected.

        editor_scrollbar = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=self.editor_text.yview)
        self.editor_text.configure(yscrollcommand=editor_scrollbar.set)
        editor_scrollbar.pack(side="left", fill="y")
        
        self.save_button = ttk.Button(editor_frame, text="Save Changes", command=self.save_from_editor, state="disabled")
        self.save_button.pack(pady=10, anchor="n")

        # --- Bottom Status Bar ---
        self.status_bar = ttk.Label(self, text="Open an I2Languages JSON file to begin, or drag & drop a file here.", relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # --- Bind keyboard shortcuts ---
        self.bind("<Control-o>", lambda event: self.open_file_dialog())
        self.bind("<Control-s>", lambda event: self.save_file())
        self.bind("<Control-S>", lambda event: self.save_file_as()) # Capital S for Shift+S

    def on_tree_select(self, event):
        """
        Called when a user selects a row in the treeview.
        It populates the text editor with the full translation text for the selected term.
        """
        selected_items = self.tree.selection()
        if not selected_items:
            # If nothing is selected (e.g., on clear), disable the editor.
            self.editor_text.config(state="normal")
            self.editor_text.delete("1.0", "end")
            self.editor_text.config(state="disabled")
            self.save_button.config(state="disabled")
            self.currently_editing_term_key = None
            return

        # Get the term key from the selected treeview item.
        item_id = selected_items[0]
        item_values = self.tree.item(item_id, "values")
        term_key = item_values[1]
        
        # Get the full original text from our main data structure, not the treeview preview.
        lang_index = self._get_selected_language_index()
        original_index = self.term_to_original_index.get(term_key)

        if lang_index is None or original_index is None:
            return # Exit if data is not ready.

        try:
            full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]
        except (KeyError, IndexError):
            full_text = "" # Handle cases where a translation is missing.

        # Update the text editor widget.
        self.editor_text.config(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", full_text)
        self.save_button.config(state="normal")
        self.currently_editing_term_key = term_key # Remember which term we are editing.

    def save_from_editor(self):
        """
        Saves the text from the editor back into the main data structure and updates the treeview.
        """
        if not self.currently_editing_term_key:
            return
        
        new_text = self.editor_text.get("1.0", "end-1c") # Get text, excluding the final newline.
        self.update_data_and_tree(self.currently_editing_term_key, new_text)
        self.status_bar.config(text=f"Saved changes for term: {self.currently_editing_term_key}")

    def on_drop(self, event):
        """
        Handles the file drop event. It cleans the file path and loads the file.
        """
        try:
            # The event.data contains the file path, which might be wrapped in curly braces on Windows.
            filepath = self.tk.splitlist(event.data)[0]
            if filepath.startswith('{') and filepath.endswith('}'):
                filepath = filepath[1:-1]
            
            self.load_file_logic(filepath)
        except Exception as e:
            messagebox.showerror("Drag & Drop Error", f"Could not open the dropped file.\n\nError: {e}")
            self.status_bar.config(text="Drag & drop failed.")

    def open_file_dialog(self):
        """
        Opens a standard file dialog to select a JSON file.
        """
        filepath = filedialog.askopenfilename(
            title="Open I2Languages JSON File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        self.load_file_logic(filepath)

    def load_file_logic(self, filepath):
        """
        The core logic for loading and parsing the I2Languages JSON file.
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            
            # The terms data can be in a few different nested structures. This code checks common locations.
            self.terms_list_ref = None
            if 'mSource' in self.data and isinstance(self.data.get('mSource'), dict) and 'mTerms' in self.data['mSource']:
                self.terms_list_ref = self.data['mSource']['mTerms'].get('Array')
            elif 'mTerms' in self.data and isinstance(self.data.get('mTerms'), dict):
                 self.terms_list_ref = self.data['mTerms'].get('Array')
            
            if self.terms_list_ref is None:
                raise ValueError("Invalid I2Languages file structure. Could not find the 'mTerms' array.")

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
        """
        Detects the number of languages in the file and tries to identify English to set as the default.
        """
        self.language_names = []
        self.detected_english_index = None

        if not self.terms_list_ref:
            self.status_bar.config(text="Warning: File contains no terms.")
            return

        # Assume all terms have the same number of languages based on the first term.
        num_languages = len(self.terms_list_ref[0].get('Languages', {}).get('Array', []))
        self.language_names = [f"Language {i+1}" for i in range(num_languages)]

        # Try to find English by looking for common, untranslated terms like 'Cancel' or 'RUN'.
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
                if found_english: break
            if found_english: break
        
        # Update the language combobox with the detected languages.
        self.language_combo.config(values=self.language_names, state="readonly")
        
        if self.detected_english_index is not None:
            self.language_var.set(self.language_names[self.detected_english_index])
        elif self.language_names:
            self.language_var.set(self.language_names[0])
        else:
             self.language_combo.config(state="disabled")

    def _get_selected_language_index(self):
        """
        Helper function to get the numerical index (0-based) from the selected language string (e.g., "Language 1").
        """
        selected_lang_str = self.language_var.get()
        if not selected_lang_str:
            return None
        try:
            return int(selected_lang_str.split(' ')[1]) - 1
        except (IndexError, ValueError):
            return None

    def populate_treeview(self):
        """
        Clears and fills the treeview with data for the currently selected language.
        """
        if not self.data or not self.terms_list_ref: return
        self.tree.delete(*self.tree.get_children())
        self.term_to_tree_item.clear()
        self.term_to_original_index.clear()
        
        # Clear and disable the editor when reloading the table.
        self.on_tree_select(None)
        
        lang_index = self._get_selected_language_index()
        if lang_index is None:
            self.status_bar.config(text="Error: No language selected or invalid format.")
            return

        for i, term_data in enumerate(self.terms_list_ref):
            term_key = term_data.get('Term', '[NO TERM KEY]')
            try:
                full_translation = term_data.get('Languages', {}).get('Array', [])[lang_index]
            except IndexError:
                full_translation = "[NO TEXT FOR THIS LANGUAGE]"
            
            # Clean up the text for display in the treeview (single line preview).
            display_translation = full_translation.replace('\n', ' ').replace('\r', ' ').strip()
            
            # Insert the row and store references for quick access later.
            item_id = self.tree.insert("", "end", values=(i + 1, term_key, display_translation))
            self.term_to_tree_item[term_key] = item_id
            self.term_to_original_index[term_key] = i

    def on_language_change(self, event=None):
        """
        Called when the user selects a different language from the combobox.
        """
        self.populate_treeview()
        self.status_bar.config(text=f"Displaying language: {self.language_var.get()}")

    def update_data_and_tree(self, term_key, new_text):
        """
        Updates a term's translation both in the main data structure and in the treeview.
        """
        if not self.data or not self.terms_list_ref: return
        
        lang_index = self._get_selected_language_index()
        original_index = self.term_to_original_index.get(term_key)

        if lang_index is None or original_index is None: return

        # Update the data in memory (the main JSON dictionary).
        self.terms_list_ref[original_index]['Languages']['Array'][lang_index] = new_text

        # Update the preview value in the treeview as well.
        item_id = self.term_to_tree_item[term_key]
        current_values = list(self.tree.item(item_id, "values"))
        current_values[2] = new_text.replace('\n', ' ').replace('\r', ' ').strip()
        self.tree.item(item_id, values=tuple(current_values))
        
        self.status_bar.config(text=f"Updated term: {term_key}")

    def save_file(self):
        """
        Saves the current data to the existing file path.
        """
        if not self.current_filepath:
            self.save_file_as()
        else:
            self._write_to_file(self.current_filepath)

    def save_file_as(self):
        """
        Opens a "Save As" dialog to save the current data to a new file.
        """
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
        """
        The core logic for writing the JSON data to a file.
        """
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
        """
        Exports the translations for the current language to a simple TXT file.
        Each line is wrapped in quotes, with internal quotes escaped as "" to preserve data.
        """
        if not self.data:
            messagebox.showwarning("No Data", "Please open a file first before exporting.")
            return
        filepath = filedialog.asksaveasfilename(
            title="Export translations to TXT", defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                lang_index = self._get_selected_language_index()
                if lang_index is None: return

                for item_id in self.tree.get_children():
                    term_key = self.tree.item(item_id, "values")[1]
                    original_index = self.term_to_original_index[term_key]
                    full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]
                    
                    # Escape double quotes within the text and then wrap the entire string in quotes.
                    # This prevents data loss if a translation contains a quote character.
                    escaped_text = full_text.replace('"', '""')
                    quoted_text = f'"{escaped_text}"'
                    f.write(quoted_text + '\n')

            self.status_bar.config(text=f"Successfully exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Could not export file: {e}")
    
    def import_from_txt(self):
        """
        Imports translations from a TXT file, replacing the translations for the current language.
        It correctly handles text that was exported with the quoting format.
        """
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
            
            # Warn the user if the number of lines doesn't match the number of terms.
            if len(lines) != len(tree_items):
                msg = (f"The number of lines in the text file ({len(lines)}) does not match "
                       f"the number of terms in the table ({len(tree_items)}).\n\n"
                       "Do you want to proceed and import matching lines only?")
                if not messagebox.askyesno("Line Count Mismatch", msg): return
            
            count = 0
            for item_id, new_line in zip(tree_items, lines):
                term_key = self.tree.item(item_id, "values")[1]
                
                # Process the line to handle the special quoting format.
                processed_line = new_line.rstrip('\n\r')
                if processed_line.startswith('"') and processed_line.endswith('"'):
                    # If it's a quoted string, remove outer quotes and un-escape inner quotes.
                    new_text = processed_line[1:-1].replace('""', '"')
                else:
                    # For backward compatibility, if not quoted, use the line as is.
                    new_text = processed_line
                
                self.update_data_and_tree(term_key, new_text)
                count += 1
            
            # Refresh the editor if an item is currently selected to show the imported text.
            selected = self.tree.selection()
            if selected:
                self.on_tree_select(None) # Trigger a fake de-select to clear the editor.
                self.tree.selection_set(selected) # Re-select the item.

            self.status_bar.config(text=f"Successfully imported {count} lines from {filepath}")
        except Exception as e:
            messagebox.showerror("Import Error", f"Could not import file: {e}")

    def find_next(self):
        """
        Finds the next occurrence of the search query in the full translation text.
        """
        query = self.search_entry.get()
        if not query: return
        
        all_items = self.tree.get_children()
        if not all_items: return

        # Start search from the item AFTER the currently selected one.
        selected_item = self.tree.focus()
        start_index = 0
        if selected_item:
            start_index = self.tree.index(selected_item) + 1

        # Create a re-ordered list to search from the start_index to the end, then wrap around to the beginning.
        items_to_search = all_items[start_index:] + all_items[:start_index]

        lang_index = self._get_selected_language_index()
        if lang_index is None: return

        for item in items_to_search:
            # Search in the full text from the data source, not just the treeview preview.
            term_key = self.tree.item(item, "values")[1]
            original_index = self.term_to_original_index[term_key]
            full_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]

            if query.lower() in full_text.lower():
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item) # Scroll to make the found item visible.
                self.status_bar.config(text=f"Found '{query}'")
                return
        
        self.status_bar.config(text=f"No more occurrences of '{query}' found.")
        messagebox.showinfo("Search Finished", f"No more occurrences of '{query}' were found.")

    def replace_selected(self):
        """
        Replaces the first occurrence of the search query within the text editor for the selected row.
        This does NOT save the change; the user must click "Save Changes".
        """
        if not self.tree.focus():
            messagebox.showinfo("Info", "Please select a row to replace.")
            return

        query = self.search_entry.get()
        replace_with = self.replace_entry.get()
        
        if not query or self.editor_text.cget("state") == "disabled":
            return

        # Replace only the first occurrence (count=1) in the editor's current text, case-insensitively.
        current_text = self.editor_text.get("1.0", "end-1c")
        new_text, count = re.subn(re.escape(query), replace_with, current_text, count=1, flags=re.IGNORECASE)
        
        if count > 0:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", new_text)
            self.status_bar.config(text="Replaced text in editor. Click 'Save Changes' to commit.")
        else:
            self.status_bar.config(text="Search text not found in the editor for the selected row.")

    def replace_all(self):
        """
        Replaces ALL occurrences of the search query in ALL terms for the current language.
        This action is permanent and saves directly to the data.
        """
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
            term_key = self.tree.item(item_id, "values")[1]
            
            # Get the full text, perform the replacement, and then update.
            original_index = self.term_to_original_index[term_key]
            old_text = self.terms_list_ref[original_index]['Languages']['Array'][lang_index]

            # Use re.subn which returns the new string and the number of substitutions made.
            new_text, num_replacements = re.subn(re.escape(query), replace_with, old_text, flags=re.IGNORECASE)

            if num_replacements > 0:
                self.update_data_and_tree(term_key, new_text)
                count += num_replacements
        
        # Refresh the editor if the currently edited item was changed during the "replace all".
        if self.currently_editing_term_key:
            selected = self.tree.selection()
            if selected:
                self.on_tree_select(None)
                self.tree.selection_set(selected)

        self.status_bar.config(text=f"Replaced {count} occurrence(s) in total.")
        messagebox.showinfo("Replace All", f"Finished. Replaced {count} occurrence(s).")


if __name__ == "__main__":
    app = I2Editor()
    app.mainloop()
