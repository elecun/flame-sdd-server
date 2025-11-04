#!/usr/bin/env python3
"""
ZMQ Connection Editor
A GUI tool to visualize and edit ZMQ connections between components in bundle configurations.
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import glob
from typing import Dict, List, Tuple, Any

class ZMQConnectionEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ZMQ Connection Editor")
        self.root.geometry("1400x900")
        
        # Data structures
        self.bundle_configs = {}  # filename -> config data
        self.connections = []     # list of (source, target, connection_info)
        self.graph = nx.DiGraph()
        
        # GUI setup
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the main GUI layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Top frame for controls
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Load directory button
        ttk.Button(control_frame, text="Load Bundle Directory", 
                  command=self.load_directory).pack(side=tk.LEFT, padx=(0, 10))
        
        # Save all button
        ttk.Button(control_frame, text="Save All Changes", 
                  command=self.save_all_configs).pack(side=tk.LEFT, padx=(0, 10))
        
        # Refresh graph button
        ttk.Button(control_frame, text="Refresh Graph", 
                  command=self.update_graph).pack(side=tk.LEFT, padx=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(control_frame, text="No directory loaded")
        self.status_label.pack(side=tk.RIGHT)
        
        # Left panel for file list and connection details
        left_panel = ttk.Frame(main_frame, width=400)
        left_panel.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        
        # File list
        ttk.Label(left_panel, text="Bundle Files:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        file_frame = ttk.Frame(left_panel)
        file_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(0, weight=1)
        
        self.file_listbox = tk.Listbox(file_frame)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        
        file_scrollbar = ttk.Scrollbar(file_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        file_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        # Connection details
        ttk.Label(left_panel, text="Connection Details:").grid(row=2, column=0, sticky=tk.W, pady=(20, 5))
        
        details_frame = ttk.Frame(left_panel)
        details_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        details_frame.columnconfigure(1, weight=1)
        
        # Connection editing fields
        self.connection_vars = {}
        fields = [
            ("Socket Name:", "socket_name"),
            ("Transport:", "transport"),
            ("Host:", "host"),
            ("Port:", "port"),
            ("Socket Type:", "socket_type"),
            ("Queue Size:", "queue_size")
        ]
        
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(details_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar()
            self.connection_vars[var_name] = var
            entry = ttk.Entry(details_frame, textvariable=var, width=30)
            entry.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
            
        # Update connection button
        ttk.Button(details_frame, text="Update Connection", 
                  command=self.update_connection).grid(row=len(fields), column=0, columnspan=2, pady=10)
        
        # Right panel for graph visualization
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        
        # Graph canvas
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Graph interaction
        self.canvas.mpl_connect('button_press_event', self.on_graph_click)
        
        # Current selection
        self.selected_file = None
        self.selected_socket = None
        
    def load_directory(self):
        """Load all JSON files from a selected directory"""
        directory = filedialog.askdirectory(
            title="Select Bundle Directory",
            initialdir="/Users/byunghunhwang/dev/flame-sdd-server/bin/x86_64"
        )
        
        if not directory:
            return
            
        # Find all JSON files
        json_files = glob.glob(os.path.join(directory, "*.json"))
        
        if not json_files:
            messagebox.showwarning("No Files", "No JSON files found in the selected directory.")
            return
            
        # Load configurations
        self.bundle_configs = {}
        self.file_listbox.delete(0, tk.END)
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    filename = os.path.basename(json_file)
                    self.bundle_configs[filename] = {
                        'path': json_file,
                        'config': config
                    }
                    self.file_listbox.insert(tk.END, filename)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load {json_file}: {str(e)}")
                
        self.status_label.config(text=f"Loaded {len(self.bundle_configs)} files from {os.path.basename(directory)}")
        self.analyze_connections()
        self.update_graph()
        
    def analyze_connections(self):
        """Analyze all connections between components"""
        self.connections = []
        
        # Create a mapping of port -> (component, socket_name, socket_info)
        port_map = {}
        
        for filename, bundle_data in self.bundle_configs.items():
            config = bundle_data['config']
            component_name = filename.replace('.json', '')
            
            if 'dataport' not in config:
                continue
                
            for socket_name, socket_info in config['dataport'].items():
                if 'port' in socket_info:
                    port = socket_info['port']
                    host = socket_info.get('host', '127.0.0.1')
                    transport = socket_info.get('transport', 'tcp')
                    socket_type = socket_info.get('socket_type', 'unknown')
                    
                    key = f"{transport}://{host}:{port}"
                    
                    if key not in port_map:
                        port_map[key] = []
                    
                    port_map[key].append({
                        'component': component_name,
                        'socket_name': socket_name,
                        'socket_info': socket_info,
                        'filename': filename
                    })
        
        # Find connections (pub-sub, push-pull pairs)
        for port_key, sockets in port_map.items():
            if len(sockets) < 2:
                continue
                
            # Group by socket type
            publishers = [s for s in sockets if s['socket_info'].get('socket_type') in ['pub', 'push']]
            subscribers = [s for s in sockets if s['socket_info'].get('socket_type') in ['sub', 'pull']]
            
            # Create connections
            for pub in publishers:
                for sub in subscribers:
                    self.connections.append({
                        'source': pub,
                        'target': sub,
                        'port_key': port_key
                    })
    
    def update_graph(self):
        """Update the graph visualization"""
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        
        if not self.connections:
            ax.text(0.5, 0.5, 'No connections found\nLoad a bundle directory first', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=14)
            self.canvas.draw()
            return
        
        # Create graph
        self.graph = nx.DiGraph()
        
        # Add nodes and edges
        for conn in self.connections:
            source_node = conn['source']['component']
            target_node = conn['target']['component']
            
            self.graph.add_node(source_node)
            self.graph.add_node(target_node)
            
            # Edge label with connection info
            source_socket = conn['source']['socket_name']
            target_socket = conn['target']['socket_name']
            port_info = conn['port_key'].split('://')[-1]  # Remove protocol
            
            edge_label = f"{source_socket} → {target_socket}\n{port_info}"
            
            self.graph.add_edge(source_node, target_node, 
                              label=edge_label,
                              connection=conn)
        
        # Layout
        try:
            pos = nx.spring_layout(self.graph, k=2, iterations=50)
        except:
            pos = nx.random_layout(self.graph)
        
        # Draw nodes
        nx.draw_networkx_nodes(self.graph, pos, ax=ax, 
                              node_color='lightblue', 
                              node_size=3000,
                              alpha=0.8)
        
        # Draw edges
        nx.draw_networkx_edges(self.graph, pos, ax=ax,
                              edge_color='gray',
                              arrows=True,
                              arrowsize=20,
                              alpha=0.6)
        
        # Draw labels
        nx.draw_networkx_labels(self.graph, pos, ax=ax, font_size=10, font_weight='bold')
        
        # Draw edge labels
        edge_labels = nx.get_edge_attributes(self.graph, 'label')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels, ax=ax, font_size=8)
        
        ax.set_title("ZMQ Component Connections", fontsize=16, fontweight='bold')
        ax.axis('off')
        
        self.canvas.draw()
    
    def on_file_select(self, event):
        """Handle file selection from listbox"""
        selection = self.file_listbox.curselection()
        if not selection:
            return
            
        filename = self.file_listbox.get(selection[0])
        self.selected_file = filename
        
        # Clear connection details
        for var in self.connection_vars.values():
            var.set("")
    
    def on_graph_click(self, event):
        """Handle clicks on the graph"""
        if event.inaxes is None:
            return
            
        # This is a simplified click handler
        # In a more sophisticated version, you'd detect which edge was clicked
        pass
    
    def update_connection(self):
        """Update a connection based on the form data"""
        if not self.selected_file:
            messagebox.showwarning("No Selection", "Please select a file first.")
            return
            
        socket_name = self.connection_vars['socket_name'].get()
        if not socket_name:
            messagebox.showwarning("No Socket", "Please enter a socket name.")
            return
            
        # Get the configuration
        config = self.bundle_configs[self.selected_file]['config']
        
        if 'dataport' not in config:
            config['dataport'] = {}
            
        if socket_name not in config['dataport']:
            config['dataport'][socket_name] = {}
            
        # Update socket configuration
        socket_config = config['dataport'][socket_name]
        
        for field, var in self.connection_vars.items():
            if field == 'socket_name':
                continue
            value = var.get().strip()
            if value:
                # Convert port and queue_size to integers
                if field in ['port', 'queue_size']:
                    try:
                        value = int(value)
                    except ValueError:
                        messagebox.showerror("Invalid Value", f"{field} must be a number.")
                        return
                socket_config[field] = value
        
        messagebox.showinfo("Updated", f"Connection {socket_name} updated in {self.selected_file}")
        
        # Refresh analysis and graph
        self.analyze_connections()
        self.update_graph()
    
    def save_all_configs(self):
        """Save all modified configurations back to files"""
        if not self.bundle_configs:
            messagebox.showwarning("No Data", "No configurations loaded.")
            return
            
        try:
            for filename, bundle_data in self.bundle_configs.items():
                with open(bundle_data['path'], 'w', encoding='utf-8') as f:
                    json.dump(bundle_data['config'], f, indent=4, ensure_ascii=False)
            
            messagebox.showinfo("Saved", f"All {len(self.bundle_configs)} configuration files saved successfully.")
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save configurations: {str(e)}")

def main():
    root = tk.Tk()
    app = ZMQConnectionEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()
