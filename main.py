# main.py
# Otak utama aplikasi MSWCD Explorer (Versi Final)

import json
import os
import math
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import NumericProperty
from kivy.utils import platform

# Import dari KivyMD
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.list import TwoLineAvatarIconListItem, IRightBodyTouch, OneLineListItem, IconLeftWidget, OneLineIconListItem
from kivymd.uix.textfield import MDTextField

# Import dari pustaka lain
from kivy_garden.mapview import MapView, MapMarkerPopup
from plyer import gps

# (Opsional) Mengatur ukuran window untuk testing di PC
Window.size = (360, 740)

# --- Kelas-kelas Pembantu untuk Dialog ---

class AddWaypointDialogContent(MDBoxLayout):
    """Konten untuk dialog tambah waypoint."""
    lat = NumericProperty(0)
    lon = NumericProperty(0)

class WaypointListItem(TwoLineAvatarIconListItem):
    """Item untuk daftar waypoint."""
    def __init__(self, waypoint, **kwargs):
        self.waypoint = waypoint
        super().__init__(**kwargs)
        self.text = waypoint['name']
        self.secondary_text = f"Lat: {waypoint['lat']:.4f}, Lon: {waypoint['lon']:.4f}"

class DeleteButton(IRightBodyTouch, MDIconButton):
    """Tombol hapus di daftar waypoint."""
    pass

# --- Definisi Setiap Layar (Screen) ---

class DashboardScreen(Screen):
    """Layar utama yang berisi menu modul-modul."""
    pass

class NavigasiDaratScreen(Screen):
    """Layar Navigasi Darat dengan Manajemen Waypoint."""
    
    waypoints = []
    waypoint_markers = []
    waypoints_file = "waypoints.json"
    add_waypoint_dialog = None
    waypoints_list_dialog = None
    current_lat = 0
    current_lon = 0

    def on_enter(self, *args):
        print("Memasuki modul Navigasi Darat.")
        self.load_waypoints()
        self.request_android_permissions()

    def load_waypoints(self):
        if os.path.exists(self.waypoints_file):
            with open(self.waypoints_file, 'r') as f:
                self.waypoints = json.load(f)
            print(f"{len(self.waypoints)} waypoint dimuat.")
        self.update_waypoint_markers()

    def save_waypoints(self):
        with open(self.waypoints_file, 'w') as f:
            json.dump(self.waypoints, f, indent=4)
        print("Waypoint berhasil disimpan.")

    def update_waypoint_markers(self):
        map_view = self.ids.map_view
        for marker in self.waypoint_markers:
            map_view.remove_widget(marker)
        self.waypoint_markers.clear()

        for point in self.waypoints:
            marker = MapMarkerPopup(lat=point['lat'], lon=point['lon'])
            marker.add_widget(MDRaisedButton(text=point['name'], on_release=lambda x, p=point: self.center_on_waypoint(p)))
            map_view.add_widget(marker)
            self.waypoint_markers.append(marker)
    
    def center_on_waypoint(self, waypoint):
        self.ids.map_view.center_on(waypoint['lat'], waypoint['lon'])
        print(f"Peta dipusatkan pada waypoint '{waypoint['name']}'.")

    def show_add_waypoint_dialog(self):
        current_lat, current_lon = self.ids.map_view.lat, self.ids.map_view.lon
        
        if not self.add_waypoint_dialog:
            dialog_content = AddWaypointDialogContent(lat=current_lat, lon=current_lon)
            self.add_waypoint_dialog = MDDialog(
                title="Tambah Waypoint Baru",
                type="custom",
                content_cls=dialog_content,
                buttons=[
                    MDFlatButton(text="BATAL", on_release=lambda x: self.add_waypoint_dialog.dismiss()),
                    MDRaisedButton(text="SIMPAN", on_release=lambda x: self.add_waypoint_data(dialog_content)),
                ],
            )
        else:
            self.add_waypoint_dialog.content_cls.lat = current_lat
            self.add_waypoint_dialog.content_cls.lon = current_lon
            
        self.add_waypoint_dialog.open()

    def add_waypoint_data(self, content):
        name = content.ids.waypoint_name.text
        if not name:
            content.ids.waypoint_name.error = True
            return

        new_waypoint = { "name": name, "desc": content.ids.waypoint_desc.text, "lat": self.ids.map_view.lat, "lon": self.ids.map_view.lon }
        self.waypoints.append(new_waypoint)
        self.save_waypoints()
        self.update_waypoint_markers()
        self.add_waypoint_dialog.dismiss()
        
        content.ids.waypoint_name.text, content.ids.waypoint_desc.text = "", ""

    def show_waypoints_list(self):
        from kivymd.uix.list import MDList
        from kivymd.uix.scrollview import MDScrollView
        
        list_content = MDScrollView()
        list_view = MDList()
        for point in self.waypoints:
            item = WaypointListItem(waypoint=point, on_release=lambda x, p=point: self.center_on_waypoint_from_list(p))
            delete_button = DeleteButton(icon="trash-can-outline", on_release=lambda x, p=point: self.delete_waypoint(p))
            item.add_widget(delete_button)
            list_view.add_widget(item)
        list_content.add_widget(list_view)

        self.waypoints_list_dialog = MDDialog(
            title="Daftar Waypoint", type="custom", content_cls=list_content,
            buttons=[MDFlatButton(text="TUTUP", on_release=lambda x: self.waypoints_list_dialog.dismiss())]
        )
        self.waypoints_list_dialog.open()

    def center_on_waypoint_from_list(self, waypoint):
        self.center_on_waypoint(waypoint)
        self.waypoints_list_dialog.dismiss()

    def delete_waypoint(self, waypoint_to_delete):
        self.waypoints.remove(waypoint_to_delete)
        self.save_waypoints()
        self.update_waypoint_markers()
        self.waypoints_list_dialog.dismiss()
        self.show_waypoints_list()
        print(f"Waypoint '{waypoint_to_delete['name']}' dihapus.")

    def center_on_gps(self):
        if self.current_lat != 0 and self.current_lon != 0:
            self.ids.map_view.center_on(self.current_lat, self.current_lon)
        else:
            print("Belum ada data GPS untuk dipusatkan.")

    def request_android_permissions(self):
        if platform != 'android':
            self.start_gps_updates()
            return
        from android.permissions import request_permissions, Permission
        def callback(permissions, results):
            if all(results):
                self.start_gps_updates()
        request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION], callback)

    def start_gps_updates(self):
        try:
            gps.configure(on_location=self.on_gps_location, on_status=self.on_gps_status)
            gps.start(minTime=1000, minDistance=1)
        except NotImplementedError:
            print("GPS tidak didukung di platform ini.")

    def on_gps_location(self, **kwargs):
        self.current_lat = kwargs.get('lat', 0.0)
        self.current_lon = kwargs.get('lon', 0.0)
        self.ids.lat_label.text = f"Lat: {self.current_lat:.6f}"
        self.ids.lon_label.text = f"Lon: {self.current_lon:.6f}"
        self.ids.alt_label.text = f"Alt: {kwargs.get('altitude', 0.0):.1f} m"
        self.ids.speed_label.text = f"Kec: {kwargs.get('speed', 0.0) * 3.6:.1f} km/j"
        self.ids.acc_label.text = f"Akurasi: {kwargs.get('accuracy', 0.0):.1f} m"

    def on_gps_status(self, stype, status):
        print(f"Status GPS: tipe='{stype}', status='{status}'")
        
    def on_leave(self, *args):
        print("Meninggalkan Navigasi Darat. Mematikan GPS.")
        gps.stop()

    def toggle_tracking(self):
        app = MDApp.get_running_app()
        track_button = self.ids.track_button
        if track_button.icon == 'record':
            track_button.icon, track_button.md_bg_color = 'stop', (1, 0, 0, 1)
        else:
            track_button.icon, track_button.md_bg_color = 'record', app.theme_cls.primary_color

class CavingScreen(Screen):
    survey_data = []
    survey_file = "caving_survey.json"
    
    def on_enter(self, *args):
        self.survey_data.clear()
        self.ids.station_list.clear_widgets()
        self.update_cave_map()

    def add_station_data(self):
        try:
            data = {
                'from': self.ids.station_from.text, 'to': self.ids.station_to.text,
                'dist': float(self.ids.distance.text), 'azi': float(self.ids.azimuth.text),
                'clino': float(self.ids.clino.text), 'left': float(self.ids.lrud_left.text),
                'right': float(self.ids.lrud_right.text), 'up': float(self.ids.lrud_up.text),
                'down': float(self.ids.lrud_down.text)
            }
            self.survey_data.append(data)
            self.refresh_log_and_map()
            for field_id in ['station_from', 'station_to', 'distance', 'azimuth', 'clino', 'lrud_left', 'lrud_right', 'lrud_up', 'lrud_down']:
                self.ids[field_id].text = ""
        except ValueError:
            self.show_alert_dialog("Error", "Data tidak valid! Pastikan semua field numerik diisi.")

    def save_survey_data(self):
        if not self.survey_data:
            self.show_alert_dialog("Info", "Tidak ada data untuk disimpan.")
            return
        with open(self.survey_file, 'w') as f:
            json.dump(self.survey_data, f, indent=4)
        self.show_alert_dialog("Berhasil", "Proyek survei berhasil disimpan!")

    def load_survey_data(self):
        if not os.path.exists(self.survey_file):
            self.show_alert_dialog("Gagal", "Tidak ada file proyek yang tersimpan.")
            return
        with open(self.survey_file, 'r') as f:
            self.survey_data = json.load(f)
        self.refresh_log_and_map()
        self.show_alert_dialog("Berhasil", "Proyek survei berhasil dimuat!")

    def refresh_log_and_map(self):
        self.ids.station_list.clear_widgets()
        for station in self.survey_data:
            log_entry = f"St: {station['from']}-{station['to']}, Dist: {station['dist']}m, Azi: {station['azi']}°"
            self.ids.station_list.add_widget(OneLineListItem(text=log_entry))
        self.update_cave_map()

    def show_alert_dialog(self, title, text):
        dialog = MDDialog(
            title=title, text=text,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())],
        )
        dialog.open()

    def update_cave_map(self):
        from kivy.graphics import Color, Line
        canvas_widget = self.ids.cave_map_canvas
        canvas_widget.canvas.clear()
        if not self.survey_data: return
        with canvas_widget.canvas:
            Color(1, 1, 1, 1)
            current_x, current_y = canvas_widget.width / 2, canvas_widget.height / 2
            scale = 10
            for station in self.survey_data:
                azi_rad = math.radians(90 - station['azi'])
                h_dist = station['dist'] * math.cos(math.radians(station['clino']))
                next_x = current_x + (h_dist * scale * math.cos(azi_rad))
                next_y = current_y + (h_dist * scale * math.sin(azi_rad))
                perp_rad_left = math.radians(90 - (station['azi'] - 90))
                left_x = current_x + (station['left'] * scale * math.cos(perp_rad_left))
                left_y = current_y + (station['left'] * scale * math.sin(perp_rad_left))
                perp_rad_right = math.radians(90 - (station['azi'] + 90))
                right_x = current_x + (station['right'] * scale * math.cos(perp_rad_right))
                right_y = current_y + (station['right'] * scale * math.sin(perp_rad_right))
                Line(points=[left_x, left_y, right_x, right_y], width=1.5)
                Line(points=[current_x, current_y, next_x, next_y], dash_offset=4)
                current_x, current_y = next_x, next_y

class SurvivalScreen(Screen): pass
class ManajemenScreen(Screen): pass

class MSWCDExplorerApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.primary_hue = "400"
        sm = ScreenManager()
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(NavigasiDaratScreen(name='navigasi_darat'))
        sm.add_widget(CavingScreen(name='caving'))
        sm.add_widget(SurvivalScreen(name='survival'))
        sm.add_widget(ManajemenScreen(name='manajemen'))
        return sm

if __name__ == '__main__':
    MSWCDExplorerApp().run()