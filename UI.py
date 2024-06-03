from math import e
from telnetlib import NOP
import wx 
import wx.grid as gridlib
import sqlite3
import threading
from threading import Thread
from wafer_map import wm_info, wm_app, wm_core
from wafer_map.wm_constants import DataType
from PIL import Image
import WaferMap
import Model 
import time


class WaferPlotPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        #Integrate Douglas Thor's graphics panel into WaferMapV1.0 frame
        self.left_p = wx.Panel(self)
        self.right_p = wx.Panel(self)

        self.center_l = wx.Button(self.left_p, label='ReCenter Plot')
        self.center_r = wx.Button(self.right_p, label='ReCenter Plot')
        # Sizers
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.vbox_l = wx.BoxSizer(wx.VERTICAL)
        self.vbox_r = wx.BoxSizer(wx.VERTICAL)

        self.hbox_l = wx.BoxSizer(wx.HORIZONTAL)
        self.hbox_r = wx.BoxSizer(wx.HORIZONTAL)
        

        self.hbox_l.Add(wx.StaticText(self.left_p, label='Wafer map plot before prediction'), 0, wx.EXPAND | wx.ALL, 5)
        self.hbox_l.Add(self.center_l, 0, wx.ALL, 5)
        self.vbox_l.Add(self.hbox_l, 0, wx.EXPAND | wx.ALL, 5)

        self.hbox_r.Add(wx.StaticText(self.right_p, label='Wafer map plot after prediction'), 0, wx.EXPAND | wx.ALL, 5)
        self.hbox_r.Add(self.center_r, 0,wx.ALL, 5)
        self.vbox_r.Add(self.hbox_r, 0, wx.EXPAND | wx.ALL, 5)

        self.left_p.SetSizer(self.vbox_l)
        self.right_p.SetSizer(self.vbox_r)

        hbox.Add(self.left_p, 1, wx.EXPAND | wx.ALL, 5)
        hbox.Add(self.right_p, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(hbox)
        return  
    
    def Update(self, db_name, mid ):
        # Remove the graphical panels in case they exist
        try:
            self.vbox_l.Detach(self.left_panel)
            self.vbox_r.Detach(self.right_panel)
        
            # Destroy the panel
            self.left_panel.Destroy()
            self.right_panel.Destroy()
        
            self.left_panel = None
            self.right_panel = None
        except:
            print("First plotting attempt")
            
        # Create a new connection to avoid thread-safty issues
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
    
        #retrive wafer information
        cursor.execute(f'SELECT * FROM wafer_config WHERE MasterID = ?', (mid,))
        wafer_tuple = cursor.fetchall()[0]
        

        #create a WaferInfo instance
        wafer_info = wm_info.WaferInfo(
            (wafer_tuple[4], wafer_tuple[3]),  # Die Size in (X, Y)
            (wafer_tuple[6], wafer_tuple[7]),  # Center Coord (X, Y)
            wafer_tuple[2],  # Wafer Diameter
            1,  # Edge Exclusion
            40,  # Flat Exclusion
        )
       #retrive data before prediction
        cursor.execute(f'SELECT DieX, DieY, HardwareBin, passing FROM die_info WHERE MasterID = ?', (mid,))
        num_xyd = cursor.fetchall()
  
        xyd = [(_x, _y, (str(_bin)+(" / PASS" if _passing == 1 else " / FAIL"))) for _x, _y, _bin, _passing in num_xyd]
        self.left_panel = wm_core.WaferMapPanel(
            self.left_p,
            xyd,
            wafer_info,
            data_type=DataType.DISCRETE,
            show_die_gridlines=False,
        )
        
        
        #retrive data before prediction
        cursor.execute(f'SELECT DieX, DieY, HardwareBin, passing FROM temporary_data WHERE MasterID = ?', (mid,))
        num_xyd = cursor.fetchall()
    
        xyd = [(_x, _y, (str(_bin)+(" / PASS" if _passing == 1 else " / FAIL"))) for _x, _y, _bin, _passing in num_xyd]
        self.right_panel = wm_core.WaferMapPanel(
            self.right_p,
            xyd,
            wafer_info,
            data_type=DataType.DISCRETE,
            show_die_gridlines=False,
        )
        
        cursor.close()
        conn.close()
        
        self.center_l.Bind(wx.EVT_BUTTON, self.on_center_l_click)
        self.center_r.Bind(wx.EVT_BUTTON, self.on_center_r_click)

        self.vbox_l.Add(self.left_panel, 1, wx.EXPAND | wx.ALL, 5)

        self.vbox_r.Add(self.right_panel, 1, wx.EXPAND | wx.ALL, 5)


        self.left_p.SetSizer(self.vbox_l)
        self.right_p.SetSizer(self.vbox_r)

        self.left_p.Layout()
        self.right_p.Layout()
        self.Layout()
        print("plots updated")
        return    
    
    def on_center_l_click(self,event):
        self.left_panel.zoom_fill()
    def on_center_r_click(self,event):
        self.right_panel.zoom_fill()
        
class WaferMapVisPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        # Load the image
        
        # Sizers        
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.img_sizer = wx.BoxSizer(wx.HORIZONTAL)
        vbox.Add(wx.StaticText(self, label='Visualizations and charts'), 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.img_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(vbox)
        
    def Update(self, figure_list = []):
        # Clear previous images
        self.img_sizer.Clear(True)
        
        for buffer in figure_list:
            # Use PIL to open the image from the buffer
            image = Image.open(buffer)
            width, height = image.size
            # Convert PIL image to wx.Image
            wx_image = wx.Image(width, height)
            wx_image.SetData(image.convert('RGB').tobytes())
            wx_image.SetAlpha(image.convert('RGBA').tobytes()[3::4])
            
            # Resize the wx.Image
            new_width = int((width/2)*1.2)
            new_height = int((height/2)*1.2)
            wx_image = wx_image.Rescale(new_width, new_height, wx.IMAGE_QUALITY_HIGH)
            
            # Convert wx.Image to wx.Bitmap and display it in the StaticBitmap
            self.image_ctrl = wx.StaticBitmap(self, wx.ID_ANY, wx.Bitmap(wx_image))
            self.img_sizer.Add(self.image_ctrl, 0, wx.ALL | wx.CENTER, 10)

        # Redraw the panel
        #self.SetSizer(self.hbox)    
        self.Layout()         
        
class WaferMapMainPanel(wx.Panel):
     def __init__(self,parent):
        super().__init__(parent)
        self.vis_panel = WaferMapVisPanel(self)
        self.wafer_info_panel = WaferInformationPanel(self)
        
        self.model_pan = ModelPanel(self)
        self.die_info_pan = DieInfoPanel(self)
        
        hbox_ = wx.BoxSizer(wx.HORIZONTAL)
        hbox_.Add(self.wafer_info_panel,1, wx.ALL | wx.EXPAND, 9)
        hbox_.Add(self.vis_panel, 6, wx.ALL | wx.EXPAND, 9)
        

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.model_pan, 1, wx.ALL | wx.EXPAND, 9)
        hbox.Add(self.die_info_pan,2, wx.ALL | wx.EXPAND, 9)
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox_, 1, wx.ALL | wx.EXPAND, 9)
        vbox.Add(hbox,2, wx.ALL | wx.EXPAND, 9)
        
        self.SetSizer(vbox)
         
class ModelPanel(wx.Panel):
     def __init__(self,parent):
        super().__init__(parent)
        
        # Outputs
        lbl1 = wx.StaticText(self, label='Model Outputs: Number of Outliers')
        self.outlier_txt = wx.TextCtrl(self)
        self.outlier_txt.SetEditable(False)
        
        # Inputs
        lbl2 = wx.StaticText(self, label='Model inputs (Optional)')
        self.kernel_txt = wx.TextCtrl(self)
        self.gamma_txt = wx.TextCtrl(self)
        self.nu_txt = wx.TextCtrl(self)
        
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self, label='Kernel: '), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        hbox.Add(self.kernel_txt, 1, wx.ALL | wx.EXPAND, 3)
        hbox.Add(wx.StaticText(self, label='Gamma: '), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        hbox.Add(self.gamma_txt, 1, wx.ALL | wx.EXPAND, 3)
        hbox.Add(wx.StaticText(self, label='Nu: '), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 3)
        hbox.Add(self.nu_txt, 1, wx.ALL | wx.EXPAND, 3)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(lbl1, 1, wx.ALL | wx.EXPAND, 3)
        vbox.Add(self.outlier_txt, 1, wx.ALL | wx.EXPAND, 3)
        vbox.Add(lbl2, 1, wx.ALL | wx.EXPAND, 3)
        vbox.Add(hbox, 1, wx.ALL | wx.EXPAND, 3)
  
        
        self.SetSizer(vbox)
        
class WaferInformationPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        

        # Add text area to show wafer ID
        label_wid = wx.StaticText(self, label="Wafer ID")
        self.wid_txt = wx.TextCtrl(self)
        
        # Add text area to show Lot ID
        label_lid = wx.StaticText(self, label="Lot ID")
        self.lid_txt = wx.TextCtrl(self)
        


        # Actual Label to show data from file
        label_before = wx.StaticText(self, label="Data Before Prediction")
        
        # Add text area to show number of good dies
        label_gdb = wx.StaticText(self, label="Good Dies: ")
        self.gdb_txt = wx.TextCtrl(self)
        
        # Add text area to show number of bad dies
        label_bdb = wx.StaticText(self, label="Bad Dies:   ")
        self.bdb_txt = wx.TextCtrl(self)

        #yield
        label_yield = wx.StaticText(self, label="Yield:      ")
        self.yield_txt = wx.TextCtrl(self)
                


        # Predict Label to show data from file
        label_after = wx.StaticText(self, label="Data After Prediction")
        
        # Add text area to show number of good dies
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        label_gda = wx.StaticText(self, label="Good Dies: ")
        self.gda_txt = wx.TextCtrl(self)
        
        # Add text area to show number of bad dies
        label_bda = wx.StaticText(self, label="Bad Dies:   ")
        self.bda_txt = wx.TextCtrl(self)
        
        #yield
        label_yield_a = wx.StaticText(self, label="Yield:      ")
        self.yield_txt_a = wx.TextCtrl(self)

        # Disable editing
        self.wid_txt.SetEditable(False)
        self.lid_txt.SetEditable(False)
        self.gdb_txt.SetEditable(False)        
        self.bdb_txt.SetEditable(False)
        self.yield_txt.SetEditable(False)
        self.gda_txt.SetEditable(False)
        self.bda_txt.SetEditable(False)
        self.yield_txt_a.SetEditable(False)

        # Sizers
        # Create sizers
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox_l_t = wx.BoxSizer(wx.HORIZONTAL)
        vbox_l = wx.BoxSizer(wx.VERTICAL)
        vbox_t = wx.BoxSizer(wx.VERTICAL)
        
        # Label
        vbox.Add(wx.StaticText(self, label='Wafer information panel'), 2, wx.EXPAND | wx.ALL, 5)
        # WID and LID Widgets
        vbox.Add(label_wid,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox.Add(self.wid_txt,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox.Add(label_lid,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox.Add(self.lid_txt,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        
        # Data before prediction
        vbox.Add(label_before,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        
        vbox_l.Add(label_gdb,0, wx.ALL | wx.CENTER | wx.EXPAND, 8)
        vbox_t.Add(self.gdb_txt,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_l.Add(label_bdb,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_t.Add(self.bdb_txt,0, wx.ALL | wx.EXPAND | wx.CENTER, 7)
        vbox_l.Add(label_yield,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_t.Add(self.yield_txt,0, wx.ALL |  wx.CENTER | wx.EXPAND, 7)
        
        hbox_l_t.Add(vbox_l,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        hbox_l_t.Add(vbox_t,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox.Add(hbox_l_t,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)

        # Data after prediction
        hbox_l_t = wx.BoxSizer(wx.HORIZONTAL)
        vbox_l = wx.BoxSizer(wx.VERTICAL)
        vbox_t = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(label_after,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_l.Add(label_gda,0, wx.ALL | wx.CENTER | wx.EXPAND, 8)
        vbox_t.Add(self.gda_txt,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_l.Add(label_bda,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_t.Add(self.bda_txt,0, wx.ALL | wx.EXPAND | wx.CENTER, 7)
        vbox_l.Add(label_yield_a,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox_t.Add(self.yield_txt_a,0, wx.ALL |  wx.CENTER | wx.EXPAND, 7)
        
        hbox_l_t.Add(vbox_l,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        hbox_l_t.Add(vbox_t,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        vbox.Add(hbox_l_t,0, wx.ALL | wx.CENTER | wx.EXPAND, 7)
        
        #self.SetBackgroundColour(wx.Colour(239, 241, 243))    
        self.SetSizer(vbox) 
        
    def Update(self, lid, wid, count_df):
        mid = count_df['MasterID']
        
        # Query to fetch wafer id and lot id
        self.lid_txt.SetValue(lid)
        self.wid_txt.SetValue(wid)
        
        self.gdb_txt.SetValue(str(count_df['good_die_count_before'][0])) 
        self.bdb_txt.SetValue(str(count_df['bad_die_count_before'][0])) 
        yield_ = (count_df['good_die_count_before'][0] / count_df['die_count'][0])*100
        yield_ = "%.2f" % yield_
        self.yield_txt.SetValue(str(yield_)+" %")  
        

        self.gda_txt.SetValue(str(count_df['good_die_count_after'][0])) 
        self.bda_txt.SetValue(str(count_df['bad_die_count_after'][0])) 
        yield_ = (count_df['good_die_count_after'][0] / count_df['die_count'][0])*100
        yield_ = "%.2f" % yield_
        self.yield_txt_a.SetValue(str(yield_)+" %")
      
class DieInfoPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Create a grid
        self.grid = gridlib.Grid(self)
        self.grid.CreateGrid(1, 13)  # 1 row, 13 columns

        # Set column labels
        self.grid.SetColLabelValue(0, "Master ID")
        self.grid.SetColLabelValue(1, "Die ID")
        self.grid.SetColLabelValue(2, "Die X Coords")
        self.grid.SetColLabelValue(3, "Die Y Coords")
        self.grid.SetColLabelValue(4, "Site Number")
        self.grid.SetColLabelValue(5, "Hardware Bin")
        self.grid.SetColLabelValue(6, "Software Bin")
        self.grid.SetColLabelValue(7, "Part Flag")
        self.grid.SetColLabelValue(8, "Passing")
        self.grid.SetColLabelValue(9, "Visited")
        self.grid.SetColLabelValue(10, "Yield")
        self.grid.SetColLabelValue(11, "Distance from center")
        self.grid.SetColLabelValue(12, "Good neighbors")
        
        self.grid.SetDefaultColSize(85)

        # Add a sizer to manage the layout of child widgets
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label = 'Search Results'), 0, wx.EXPAND)
        sizer.Add(self.grid, 1, wx.EXPAND)

        # Set the sizer for the panel
        self.SetSizer(sizer)
    def Update(self, data):
        for index, item in enumerate(data):
            print(len(data))
            self.grid.SetCellValue(0, index, str(item))
            


class SearchBarPanel(wx.Panel):
    def __init__(self, parent, db_name):
        super(SearchBarPanel, self).__init__(parent)
        self.parent = parent
        self.db_name = db_name
        # Set the panel's background color
        self.SetBackgroundColour(wx.Colour(240, 240, 240))

        # Create the search bar elements
        search_label = wx.StaticText(self, label="Search by Die ID:")
        self.search_ctrl = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        search_button = wx.Button(self, label="Search")

        # Bind the search button click event
        search_button.Bind(wx.EVT_BUTTON, self.on_search)

        # Bind the enter key event in the text control
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_search)

        # Create a horizontal box sizer to arrange the search bar elements
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        hbox.Add(self.search_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        hbox.Add(search_button, 0, wx.ALL, 5)

        # Set the sizer for the panel
        self.SetSizer(hbox)

    def on_search(self, event):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            if self.search_ctrl.GetValue().strip():
                cursor.execute('SELECT * FROM temporary_data WHERE MasterID = ? and DieID = ?',  (self.parent.mid, int(self.search_ctrl.GetValue().strip())))
                data = cursor.fetchall()[0]
                self.parent.main_panel.die_info_pan.Update(data) 
        except:
            wx.MessageBox(f"Die ID must be an INTEGER","Error", wx.ICON_ERROR)
        finally:
            cursor.close()    
            conn.close()
      
class PredictPanel(wx.Panel):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.mid_txt = wx.TextCtrl(self)
        self.predict_btn = wx.Button(self,label='Predict')
        #predict_btn.Bind(wx.EVT_BUTTON, self.on_predict_click)
            
        # Create a horizontal box sizer to arrange the search bar elements
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self, label='Enter Master ID instead of parsing an STDF file'), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        hbox.Add(self.mid_txt, 1, wx.ALL | wx.EXPAND, 5)
        hbox.Add(self.predict_btn, 0, wx.ALL, 5)
        self.SetSizer(hbox)

class WaferMapFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Wafer Map Towards Die Yield Enhancement')
        self._db_name = "database.db"

        # Panels
        self.predict_panel = PredictPanel(self)
        self.search_panel = SearchBarPanel(self, self._db_name)
        self.plot_panel = WaferPlotPanel(self)
        self.main_panel = WaferMapMainPanel(self)
        
        # Status bar to indicate and track the beggining and end of parsing
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText("Ready")
        
        self.predict_panel.predict_btn.Bind(wx.EVT_BUTTON, self.on_predict_click)

        hor = wx.BoxSizer(wx.HORIZONTAL)
        hor.Add(self.predict_panel, 2, wx.EXPAND)
        hor.Add(self.search_panel, 2, wx.EXPAND)
        hor.Add(self.status_bar, 1, wx.EXPAND)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.main_sizer.Add(hor, 0, wx.ALL | wx.CENTER | wx.EXPAND, 10)
        self.main_sizer.Add(self.main_panel, 0, wx.ALL | wx.CENTER | wx.EXPAND,10)
        self.main_sizer.Add(self.plot_panel, 1, wx.ALL | wx.CENTER | wx.EXPAND,10)

        self.SetSizer(self.main_sizer)
        
        self.create_menu()
        self.plot_panel.Hide()
        
        self.Show()
       
        
    def create_menu(self):
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        view_menu = wx.Menu()  # visualization menu
        
        #Append item's children
        self.open_file_menu_item = file_menu.Append(
            wx.ID_ANY, 'Open STDF File', 
            'Open a file with STDF'
        )
        
        #Append items to menu bar
        menu_bar.Append(file_menu, '&File')  #The ampersand to create a keyboard shortcut of Alt+F to open the File menu
        self.Bind(
            event=wx.EVT_MENU, 
            handler=self.on_open_folder,  # event
            source=self.open_file_menu_item, # menu item
        )
        
        switch_to_vis = view_menu.Append(wx.ID_ANY, "Switch to Visualization Panel")
        menu_bar.Append(view_menu, 'View')
        self.Bind(
            event=wx.EVT_MENU, 
            handler=self.display_vis_panel,  # event
            source=switch_to_vis, # menu item
        )
        
        switch_to_main = view_menu.Append(wx.ID_ANY, "Switch to Main Panel")
        self.Bind(
            event=wx.EVT_MENU, 
            handler=self.display_main_panel,  # event
            source=switch_to_main, # menu item
        )
        
        self.SetMenuBar(menu_bar)

    def on_open_folder(self, event):
        title = "Choose STDF File"
        dlg = wx.FileDialog(self, title, wildcard="STDF files (*.stdf)|*.stdf",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            self.save_file_dir(dlg.GetPath())
            
            try:
                #self.status_bar.SetStatusText("Process started...")
                # Call the parser/loader with the selected file path
                self.parse_thread = Thread(target=self.App_for_file_chooser)
                self.parse_thread.daemon = False
                self.parse_thread.start()

                # Start a timer to check for the thread status
                self.timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self.on_timer)
                self.timer.Start(100)
                
            except Exception as e:
                # Show an error message dialog if something goes wrong
                wx.MessageBox(f"An error occurred while processing the file: {str(e)}", "Error", wx.ICON_ERROR)


        dlg.Destroy()
        
    def on_predict_click(self, event):
        try:
            #self.status_bar.SetStatusText("Process started...")
            # Call the parser/loader with the selected file path
            self.parse_thread = Thread(target=self.App_for_mid_insertion)
            self.parse_thread.daemon = False
            self.parse_thread.start()

            # Start a timer to check for the thread status
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_timer)
            self.timer.Start(100)
                
            
        except Exception as e:
            # Show an error message dialog if something goes wrong
            wx.MessageBox(f"An error occurred while processing the file: {str(e)}", "Error", wx.ICON_ERROR)

    def on_timer(self, event):
        if not self.parse_thread.is_alive():
                self.timer.Stop()
                self.status_bar.SetStatusText("Done")
                self.predict_panel.predict_btn.Enable()
                self.MenuBar.Enable(self.open_file_menu_item.GetId(), True)
            
                try:
                    self.main_panel.model_pan.outlier_txt.SetValue(str(self.num_ouliers))
                    self.main_panel.wafer_info_panel.Update(self.lid,self.wid,self.count_df)                
                    self.plot_panel.Update(self._db_name, self.mid)
                    self.main_panel.vis_panel.Update(self.figure_list)
                    wx.MessageBox(f"Parsing is over MID: {self.mid}","Information", wx.ICON_INFORMATION)
                except Exception as e:
                    #wx.MessageBox(f"An error occurred while processing: {str(e)}", "Error", wx.ICON_ERROR)
                    NOP


    def App_for_file_chooser(self):
         try:    
            self.MenuBar.Enable(self.open_file_menu_item.GetId(), False)
            # Call parser and loader
            self.status_bar.SetStatusText("Parsing started...")
            self.predict_panel.predict_btn.Disable()
        
        
            self.mid, self.lid,self.wid = WaferMap.main(self.file_path, self._db_name)

            self.predict()
            
         except:
            wx.MessageBox(f"File is corrupted or incomplete", "Error", wx.ICON_ERROR)
        
    
    def App_for_mid_insertion(self):
        self.MenuBar.Enable(self.open_file_menu_item.GetId(), False)
        try:
            # Call parser and loader
            self.status_bar.SetStatusText("Parsing started...")
            self.predict_panel.predict_btn.Disable()
        
            self.mid = int(self.predict_panel.mid_txt.GetValue())
            conn = sqlite3.connect(self._db_name)
            cursor = conn.cursor()
            cursor.execute('SELECT LotID, WaferID FROM wafer_info WHERE MasterID = ?', (self.mid,))
            self.lid,self.wid = cursor.fetchall()[0]

            self.predict()

        except:
            wx.MessageBox(f"Master ID must be an integer. Make sure to enter an existing number","Information", wx.ICON_INFORMATION)
            
        return
    
    def predict(self):
        try:
            # Call model
            self.status_bar.SetStatusText("Prediction started...")
            
            # Check if model inputs contain a value
            kernel, gamma, nu = ('rbf', 'scale', 0.06)
        
            if self.main_panel.model_pan.kernel_txt.GetValue().strip():
                kernel = self.main_panel.model_pan.kernel_txt.GetValue().strip()
                print('kernel ', kernel)
            if self.main_panel.model_pan.gamma_txt.GetValue().strip():
                gamma = float(self.main_panel.model_pan.gamma_txt.GetValue().strip())
                print('gamma ', gamma)
            if self.main_panel.model_pan.nu_txt.GetValue().strip():
                nu = float(self.main_panel.model_pan.nu_txt.GetValue().strip())
                print('nu ', nu)
            
            self.db_string ='sqlite:///C:/Users/hp/OneDrive/Desktop/WaferMap/WaferMap/database.db'
            self.num_ouliers, self.count_df, self.figure_list = Model.main(self.db_string, self.mid,kernel = kernel, gamma = gamma, nu = nu)            

        except:
            kernel, gamma, nu = ('rbf', 'scale', 0.06)
            wx.MessageBox(f"Model inputs unvalid. Prediction will happen with default values (kernael = {kernel} , gamma = {gamma} , nu = {nu}.","Error", wx.ICON_ERROR)
            self.num_ouliers, self.count_df, self.figure_list = Model.main(self.db_string, self.mid,kernel = kernel, gamma = gamma, nu = nu)
                
    def save_file_dir(self, file_path):
        self.file_path = file_path
        
    def display_vis_panel(self,event):  # Open visualization panel 
        self.main_panel.Hide()
        self.predict_panel.Hide()
        self.search_panel.Hide()
        self.plot_panel.Show()
        self.Layout()
        
    def display_main_panel(self,event):  # Open main panel 
        self.plot_panel.Hide()
        self.main_panel.Show()
        self.predict_panel.Show()
        self.search_panel.Show()
        self.Layout()
        

def Main():
    
    #creating the application
    app = wx.App()
    
    #instantiate a frame
    frame = WaferMapFrame()
    frame.Maximize(True)
    # set the main loop to keep the window on view
    app.MainLoop()
    
    return


if __name__ == '__main__':
    st = time.time()
    Main()
    print("Total use time: ",time.time()-st," seconds")