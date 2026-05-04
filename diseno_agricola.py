# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Parcelador_COLPOS
                                 A QGIS plugin
 Agricultural production unit layout optimization for precision farming.
 ***************************************************************************/
"""

import math
import os.path
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QWidget

# Consolidated imports to avoid NameError and conflicts
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsLineSymbol, QgsFillSymbol, QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings, NULL, Qgis, QgsPointXY
)

from qgis import processing
from .resources import *
from .diseno_agricola_dialog import Parcelador_COLPOSDialog

class Parcelador_COLPOS:
    """Plugin implementation for optimized agricultural plot design."""

    def crear_geometria(self, p_centro, tipo, r_deg, ang_rot):
        """Generates rotatable geometric primitives (Square, Triangle, Circle)."""
        ang_rad = math.radians(-ang_rot)
        if tipo == "Cuadrado":
            puntos = [(-r_deg, -r_deg), (r_deg, -r_deg), (r_deg, r_deg), (-r_deg, r_deg)]
        elif tipo in ["Triángulo", "Triangulo"]:
            puntos = [(0, r_deg), (-r_deg, -r_deg / 2), (r_deg, -r_deg / 2)]
        else:
            return QgsGeometry.fromPointXY(p_centro).buffer(r_deg, 24)

        vertices = []
        for dx, dy in puntos:
            ex = p_centro.x() + dx * math.cos(ang_rad) - dy * math.sin(ang_rad)
            ey = p_centro.y() + dx * math.sin(ang_rad) + dy * math.cos(ang_rad)
            vertices.append(QgsPointXY(ex, ey))
        return QgsGeometry.fromPolygonXY([vertices])

    def rotar_punto(self, px, py, cx, cy, angulo):
        """Rotates an individual coordinate around a pivot point."""
        rad = math.radians(-angulo)
        nx = cx + (px - cx) * math.cos(rad) - (py - cy) * math.sin(rad)
        ny = cy + (px - cx) * math.sin(rad) + (py - cy) * math.cos(rad)
        return QgsPointXY(nx, ny)

    def d2xy(self, n, d):
        """Hilbert Curve transformation: distance to (x,y) coordinates."""
        t, x, y, s = d, 0, 0, 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            if ry == 0:
                if rx == 1: x, y = s - 1 - y, s - 1 - x
                x, y = y, x
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        return x, y

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&Diseño de Unidades Agrícolas Vichique')
        self.first_start = None

    def tr(self, message):
        return QCoreApplication.translate('Parcelador_COLPOS', message)

    def add_action(self, icon_path, text, callback, **kwargs):
        icon = QIcon(icon_path)
        action = QAction(icon, text, kwargs.get('parent'))
        action.triggered.connect(callback)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = ':/plugins/diseno_agricola/icon.png'
        self.add_action(icon_path, text=self.tr(u'Parcelero_Colpos'),
                        callback=self.run, parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        console_widget = self.iface.mainWindow().findChild(QWidget, 'PythonConsole')
        if console_widget:
            console_widget.setVisible(True)
        if self.first_start:
            self.first_start = False
            self.dlg = Parcelador_COLPOSDialog()

        if self.dlg.exec_():
            layer = self.dlg.mMapLayerComboBox.currentLayer()
            modo = self.dlg.comboBox_modo.currentText()
            figura = self.dlg.comboBox_geometria.currentText()
            metros = self.dlg.doubleSpinBox_grosor.value()
            pasillo = self.dlg.doubleSpinBox_pasillos.value()
            angulo = self.dlg.doubleSpinBox_angulo.value()
            densidad = int(self.dlg.doubleSpinBox_hilbert.value())
            pct_threshold = self.dlg.doubleSpinBox_descarte.value()
            draw_path = self.dlg.checkBox_ruta.isChecked()
            draw_centers = self.dlg.checkBox_centros.isChecked()
            draw_coords = self.dlg.checkBox_coordenadas.isChecked()

            if not layer:
                self.iface.messageBar().pushMessage("Error", "Invalid Layer", level=Qgis.Warning)
                return

            # Cleanup existing layers
            for n in ["Hilbert_Path", "Unit_Centers", "Etiquetas_Mosaicos", "Etiquetas_Franjas", "Capa_Coordenadas",
                      "Layout_Mosaicos", "Layout_Franjas"]:
                for c in QgsProject.instance().mapLayersByName(n):
                    QgsProject.instance().removeMapLayer(c.id())

            feat_parcela = layer.selectedFeatures()[0] if layer.selectedFeatures() else next(layer.getFeatures())
            geom_parcela = feat_parcela.geometry()
            pivot_point = geom_parcela.centroid().asPoint()
            area_total_m2 = geom_parcela.area() * (111000 ** 2)

            if modo == "Franjas":
                capa_bloques = QgsVectorLayer("Polygon?crs=EPSG:4326", "Temp_Blocks", "memory")
                pr_b = capa_bloques.dataProvider()
                n_grid = 2 ** densidad
                dist_entre_surcos = metros + pasillo
                r_deg = (metros / 2) / 111000.0

                # --- BASE GEOMETRY GENERATION ---
                for i in range(-n_grid // 2, n_grid // 2):
                    for j in range(-n_grid // 2, n_grid // 2):
                        bx_m = i * dist_entre_surcos
                        by_m = j * metros
                        p_c = self.rotar_punto(pivot_point.x() + bx_m / 111000.0,
                                               pivot_point.y() + by_m / 111000.0,
                                               pivot_point.x(), pivot_point.y(), angulo)
                        unit_geom = self.crear_geometria(p_c, "Cuadrado", r_deg, angulo)
                        if unit_geom.intersects(geom_parcela):
                            f = QgsFeature()
                            f.setGeometry(unit_geom)
                            pr_b.addFeature(f)

                # --- GEOSPATIAL PROCESSING (LOGIC CHAIN) ---
                # 1. Buffer to merge fragments
                buf_1 = \
                processing.run("native:buffer", {'INPUT': capa_bloques, 'DISTANCE': 0.0000001, 'OUTPUT': 'memory:buf'})[
                    'OUTPUT']
                # 2. Dissolve to create long strips
                res_diss = processing.run("native:dissolve", {'INPUT': buf_1, 'FIELD': [], 'OUTPUT': 'memory:diss'})[
                    'OUTPUT']
                # 3. Clip with plot boundary
                res_clip = \
                processing.run("native:clip", {'INPUT': res_diss, 'OVERLAY': layer, 'OUTPUT': 'memory:clip'})['OUTPUT']
                # 4. Explode multipart to single parts
                capa_result = \
                processing.run("native:multiparttosingleparts", {'INPUT': res_clip, 'OUTPUT': 'memory:Layout_Franjas'})[
                    'OUTPUT']

                # --- ATTRIBUTE CONFIGURATION ---
                capa_result.dataProvider().addAttributes([
                    QgsField("ID_Surco", QVariant.Int),
                    QgsField("Area_m2", QVariant.Double)
                ])
                capa_result.updateFields()

                # --- STATISTICAL CALCULATION AND CLEANUP ---
                stats = {"aptas": 0, "area_util": 0.0}
                capa_result.startEditing()
                for feature in capa_result.getFeatures():
                    f_area = feature.geometry().area() * (111000 ** 2)
                    # Discard filter (avoids tiny fragments at boundaries)
                    if f_area > (metros * 1.5):
                        stats["aptas"] += 1
                        stats["area_util"] += f_area
                        feature.setAttributes([stats["aptas"], round(f_area, 2)])
                        capa_result.updateFeature(feature)
                    else:
                        capa_result.deleteFeature(feature.id())
                capa_result.commitChanges()

                # --- RENDERING AND LABELS ---
                self.crear_capa_etiquetas(capa_result, "ID_Surco", "Etiquetas_Franjas")
                QgsProject.instance().addMapLayer(capa_result)

                # --- FINAL CONSOLE REPORT ---
                eff = (stats["area_util"] / area_total_m2) * 100 if area_total_m2 > 0 else 0
                print("\n" + "=" * 40)
                print(f"{'REPORT: ' + modo.upper():^40}")
                print("=" * 40)
                print(f"Total Area:      {area_total_m2:10.2f} m²")
                print(f"Useful Area:     {stats['area_util']:10.2f} m²")
                print(f"Efficiency:      {eff:10.2f} %")
                print(f"Total Rows:      {stats['aptas']:>10}")
                print("=" * 40)

            else:
                # Mosaics Mode
                stats = {"aptas": 0, "area_util": 0.0, "no_aptas": 0}
                n_grid = 2 ** densidad
                jump_dist = metros + pasillo
                r_deg = (metros / 2) / 111000.0
                area_ref = metros ** 2 if figura == "Cuadrado" else (math.pi * (metros / 2) ** 2)

                capa_t = QgsVectorLayer("Polygon?crs=EPSG:4326", f"Layout_{modo}", "memory")
                capa_c = QgsVectorLayer("Point?crs=EPSG:4326", "Unit_Centers", "memory")

                for c in [capa_t, capa_c]:
                    c.dataProvider().addAttributes([QgsField("ID_Unidad", QVariant.Int), QgsField("status", QVariant.String), QgsField("pct_area", QVariant.Double)])
                    c.updateFields()

                path_pts = []
                for d in range(n_grid * n_grid):
                    hx, hy = self.d2xy(n_grid, d)
                    off_x, off_y = (hx - n_grid / 2) * jump_dist, (hy - n_grid / 2) * jump_dist
                    p_c = self.rotar_punto(pivot_point.x() + off_x / 111000.0, pivot_point.y() + off_y / 111000.0, pivot_point.x(), pivot_point.y(), angulo)
                    unit_geom = self.crear_geometria(p_c, figura, r_deg, angulo)

                    if unit_geom.intersects(geom_parcela):
                        inter = unit_geom.intersection(geom_parcela)
                        f_area = inter.area() * (111000 ** 2)
                        pct = (f_area / area_ref) * 100
                        status = "Optimal (Green)" if pct >= 99.9 else ("Suitable (Yellow)" if pct >= pct_threshold else "Discarded (Red)")

                        id_numero = None
                        if pct >= pct_threshold:
                            stats["aptas"] += 1
                            stats["area_util"] += f_area
                            id_numero = stats["aptas"]
                            path_pts.append(p_c)
                            if draw_centers:
                                fc = QgsFeature(); fc.setGeometry(QgsGeometry.fromPointXY(p_c))
                                fc.setAttributes([id_numero, status, round(pct, 1)])
                                capa_c.dataProvider().addFeature(fc)
                        else:
                            stats["no_aptas"] += 1

                        f = QgsFeature(); f.setGeometry(inter); f.setAttributes([id_numero, status, round(pct, 1)])
                        capa_t.dataProvider().addFeature(f)

                if draw_path and len(path_pts) > 1:
                    capa_r = QgsVectorLayer("LineString?crs=EPSG:4326", "Hilbert_Path", "memory")
                    fr = QgsFeature(); fr.setGeometry(QgsGeometry.fromPolylineXY(path_pts))
                    capa_r.dataProvider().addFeature(fr)
                    capa_r.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({'color': '255,120,0,255', 'width': '1.0'})))
                    QgsProject.instance().addMapLayer(capa_r)

                self.aplicar_estilo_semaforo(capa_t)
                self.crear_capa_etiquetas(capa_t, "ID_Unidad", "Etiquetas_Mosaicos")
                QgsProject.instance().addMapLayer(capa_t)
                if draw_centers:
                    QgsProject.instance().addMapLayer(capa_c)
                if draw_coords:
                    self.crear_capa_coordenadas(capa_c)

                # --- 5. FINAL CONSOLE REPORT ---
                eff = (stats["area_util"] / area_total_m2) * 100 if area_total_m2 > 0 else 0

                # Define labels based on mode for report clarity
                label_units = "Total Rows:" if modo == "Franjas" else "Suitable Units (Mosaics):"

                print("\n" + "=" * 40)
                print(f"{'REPORT: ' + modo.upper():^40}")
                print("=" * 40)
                print(f"Total Area:      {area_total_m2:10.2f} m²")
                print(f"Useful Area:     {stats['area_util']:10.2f} m²")
                print(f"Efficiency:      {eff:10.2f} %")
                print(f"{label_units:<25} {stats['aptas']:>10}")

                if modo != "Franjas":
                    print(f"Discarded Units:          {stats['no_aptas']:>10}")

                print("=" * 40)

                self.iface.messageBar().pushMessage("COLPOS", f"{modo} process successfully completed",
                                                    level=Qgis.Success)

    def crear_capa_etiquetas(self, capa_origen, campo_id, nombre_capa):
        """Creates a memory layer for labeling centroids of the production units."""
        capa_lbls = QgsVectorLayer("Point?crs=EPSG:4326", nombre_capa, "memory")
        capa_lbls.dataProvider().addAttributes([QgsField("Label_ID", QVariant.String)])
        capa_lbls.updateFields()

        feats = []
        for feat in capa_origen.getFeatures():
            val = feat[campo_id]
            if val is not None and val != NULL:
                f = QgsFeature(); f.setGeometry(feat.geometry().centroid())
                f.setAttributes([str(val)]); feats.append(f)
        capa_lbls.dataProvider().addFeatures(feats)

        settings = QgsPalLayerSettings()
        settings.fieldName = "Label_ID"
        settings.placement = QgsPalLayerSettings.AroundPoint
        txt = QgsTextFormat(); txt.setSize(12); txt.setColor(QColor("black"))
        buff = QgsTextBufferSettings(); buff.setEnabled(True); buff.setSize(1)
        txt.setBuffer(buff)
        settings.setFormat(txt)
        capa_lbls.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        capa_lbls.setLabelsEnabled(True)
        capa_lbls.renderer().symbol().setSize(0)
        QgsProject.instance().addMapLayer(capa_lbls)

    def aplicar_estilo_semaforo(self, layer):
        """Applies a categorized semaphore-style symbology (Red/Yellow/Green)."""
        props = {'outline_color': 'white', 'style': 'solid'}
        cats = [
            QgsRendererCategory("Optimal (Green)", QgsFillSymbol.createSimple({'color': '76,175,80,150', **props}), "Optimal (>99%)"),
            QgsRendererCategory("Suitable (Yellow)", QgsFillSymbol.createSimple({'color': '255,235,59,150', **props}), "Suitable (Cut)"),
            QgsRendererCategory("Discarded (Red)", QgsFillSymbol.createSimple({'color': '244,67,54,150', **props}), "Discarded")
        ]
        layer.setRenderer(QgsCategorizedSymbolRenderer("status", cats))
        layer.triggerRepaint()

    def crear_capa_coordenadas(self, capa_centros):
        """Generates an independent layer with physical coordinate labels (WGS84)."""
        # 1. Create memory layer with double precision fields
        capa_coords = QgsVectorLayer("Point?crs=EPSG:4326", "Capa_Coordenadas", "memory")
        capa_coords.dataProvider().addAttributes([
            QgsField("LAT_Y", QVariant.Double),
            QgsField("LON_X", QVariant.Double)
        ])
        capa_coords.updateFields()

        # 2. Extract points and save coordinates in the attribute table
        feats = []
        for feat in capa_centros.getFeatures():
            geom = feat.geometry()
            p_point = geom.asPoint()

            f = QgsFeature()
            f.setGeometry(geom)
            # Save with 8 decimals (centimetric precision for GPS)
            f.setAttributes([round(p_point.y(), 8), round(p_point.x(), 8)])
            feats.append(f)

        capa_coords.dataProvider().addFeatures(feats)

        # 3. Dynamic labeling configuration (Visualization formula)
        settings = QgsPalLayerSettings()
        # Displays both DMS (Degree-Minute-Second) and DD (Decimal Degrees)
        settings.fieldName = "to_dms($y, 'y', 2) || ' ' || to_dms($x, 'x', 2) || '\n' || 'DD: ' || format_number($y, 6) || ', ' || format_number($x, 6)"
        #settings.fieldName = "'X: ' || format_number($x, 6) || '\n' || 'Y: ' || format_number($y, 6)"
        settings.isExpression = True
        settings.placement = QgsPalLayerSettings.AroundPoint

        # Collision and zoom control
        settings.displayAll = False
        settings.scaleVisibility = True
        settings.minimumScale = 2500

        # --- VISUAL STYLE (Black text with white buffer) ---
        txt = QgsTextFormat()
        txt.setSize(12)
        txt.setColor(QColor("black"))

        buff = QgsTextBufferSettings()
        buff.setEnabled(True)
        buff.setSize(1.0)
        buff.setColor(QColor("white"))

        txt.setBuffer(buff)
        settings.setFormat(txt)

        capa_coords.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        capa_coords.setLabelsEnabled(True)

        # 4. Set point size to 0 to avoid obscuring Unit_Centers
        capa_coords.renderer().symbol().setSize(0)

        # 5. Load to project
        QgsProject.instance().addMapLayer(capa_coords)