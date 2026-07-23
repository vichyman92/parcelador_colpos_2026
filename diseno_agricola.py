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
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QWidget

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField,
    QgsLineSymbol, QgsFillSymbol, QgsSingleSymbolRenderer,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings, NULL, Qgis, QgsPointXY
)

from qgis import processing
try:
    from .resources import *
except ImportError:
    pass

from .diseno_agricola_dialog import Parcelador_COLPOSDialog


class Parcelador_COLPOS:
    """Plugin implementation for optimized agricultural plot design."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&Diseño de Unidades Agrícolas Colpos')
        self.first_start = None
        self.dlg = None

    def tr(self, message):
        """Translate strings."""
        return QCoreApplication.translate('Parcelador_COLPOS', message)

    def add_action(self, icon_path, text, callback, **kwargs):
        """Adds action to QGIS menu/toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, kwargs.get('parent'))
        action.triggered.connect(callback)
        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Initialize GUI elements."""
        icon_path = ':/plugins/parcelador_colpos_2026/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Parcelero Colpos'),
            callback=self.run,
            parent=self.iface.mainWindow()
        )
        self.first_start = True

    def unload(self):
        """Removes plugin from QGIS."""
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

    def create_geometry(self, p_center, p_type, r_deg, rot_angle):
        """Generates rotatable geometric primitives."""
        ang_rad = math.radians(-rot_angle)
        if p_type == "Cuadrado":
            points = [
                (-r_deg, -r_deg), (r_deg, -r_deg),
                (r_deg, r_deg), (-r_deg, r_deg)
            ]
        elif p_type in ["Triángulo", "Triangulo"]:
            points = [(0, r_deg), (-r_deg, -r_deg / 2), (r_deg, -r_deg / 2)]
        else:
            return QgsGeometry.fromPointXY(p_center).buffer(r_deg, 24)

        vertices = []
        for dx, dy in points:
            ex = p_center.x() + dx * math.cos(ang_rad) - dy * math.sin(ang_rad)
            ey = p_center.y() + dx * math.sin(ang_rad) + dy * math.cos(ang_rad)
            vertices.append(QgsPointXY(ex, ey))
        return QgsGeometry.fromPolygonXY([vertices])

    def rotate_point(self, px, py, cx, cy, angle):
        """Rotates an individual coordinate around a pivot point."""
        rad = math.radians(-angle)
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
                if rx == 1:
                    x, y = s - 1 - y, s - 1 - x
                x, y = y, x
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        return x, y

    def run(self):
        """Main execution logic."""
        if self.first_start:
            self.first_start = False
            self.dlg = Parcelador_COLPOSDialog()

        if self.dlg.exec_():
            layer = self.dlg.mMapLayerComboBox.currentLayer()
            mode = self.dlg.comboBox_modo.currentText()
            shape = self.dlg.comboBox_geometria.currentText()
            thickness = self.dlg.doubleSpinBox_grosor.value()
            aisle = self.dlg.doubleSpinBox_pasillos.value()
            angle = self.dlg.doubleSpinBox_angulo.value()
            density = int(self.dlg.doubleSpinBox_hilbert.value())
            pct_threshold = self.dlg.doubleSpinBox_descarte.value()
            draw_path = self.dlg.checkBox_ruta.isChecked()
            draw_centers = self.dlg.checkBox_centros.isChecked()
            draw_coords = self.dlg.checkBox_coordenadas.isChecked()

            if not layer:
                self.iface.messageBar().pushMessage(
                    "Error", "Invalid Layer", level=Qgis.Warning
                )
                return

            # Limpieza automática de capas previas
            cleanup_layers = [
                "Hilbert_Path", "Unit_Centers", "Labels_Mosaics",
                "Labels_Strips", "Coord_Layer", "Layout_Mosaics",
                "Layout_Strips", "GPS_Guide_Lines"
            ]
            for name in cleanup_layers:
                for c in QgsProject.instance().mapLayersByName(name):
                    QgsProject.instance().removeMapLayer(c.id())

            feat_parcel = (layer.selectedFeatures()[0] if
                           layer.selectedFeatures() else
                           next(layer.getFeatures()))
            geom_parcel = feat_parcel.geometry()
            pivot = geom_parcel.centroid().asPoint()
            total_area_m2 = geom_parcel.area() * (111000 ** 2)

            if mode == "Franjas":
                capa_blocks = QgsVectorLayer(
                    "Polygon?crs=EPSG:4326", "Temp_Blocks", "memory"
                )
                pr_b = capa_blocks.dataProvider()
                n_grid = 2 ** density
                row_dist = thickness + aisle
                r_deg = (thickness / 2) / 111000.0

                capa_lines = QgsVectorLayer(
                    "LineString?crs=EPSG:4326", "GPS_Guide_Lines", "memory"
                )
                pr_l = capa_lines.dataProvider()
                pr_l.addAttributes([QgsField("Row_ID", QVariant.Int)])
                capa_lines.updateFields()

                for i in range(-n_grid // 2, n_grid // 2):
                    line_pts = []
                    for j in range(-n_grid // 2, n_grid // 2):
                        bx_m = i * row_dist
                        by_m = j * thickness
                        p_c = self.rotate_point(
                            pivot.x() + bx_m / 111000.0,
                            pivot.y() + by_m / 111000.0,
                            pivot.x(), pivot.y(), angle
                        )
                        unit_geom = self.create_geometry(
                            p_c, "Cuadrado", r_deg, angle
                        )
                        if unit_geom.intersects(geom_parcel):
                            f = QgsFeature()
                            f.setGeometry(unit_geom)
                            pr_b.addFeature(f)
                            line_pts.append(p_c)

                    if len(line_pts) > 1:
                        fl = QgsFeature()
                        fl.setGeometry(QgsGeometry.fromPolylineXY(line_pts))
                        pr_l.addFeature(fl)

                # Procesamiento espacial de franjas
                buf = processing.run("native:buffer", {
                    'INPUT': capa_blocks,
                    'DISTANCE': 0.00000001,
                    'OUTPUT': 'memory:buf'
                })['OUTPUT']
                diss = processing.run("native:dissolve", {
                    'INPUT': buf,
                    'FIELD': [],
                    'OUTPUT': 'memory:diss'
                })['OUTPUT']
                clip = processing.run("native:clip", {
                    'INPUT': diss,
                    'OVERLAY': layer,
                    'OUTPUT': 'memory:clip'
                })['OUTPUT']
                res_layer = processing.run("native:multiparttosingleparts", {
                    'INPUT': clip,
                    'OUTPUT': 'memory:Layout_Strips'
                })['OUTPUT']

                res_layer.dataProvider().addAttributes([
                    QgsField("Row_ID", QVariant.Int),
                    QgsField("Area_m2", QVariant.Double)
                ])
                res_layer.updateFields()

                stats = {"fit": 0, "cult_area": 0.0}
                res_layer.startEditing()
                for feature in res_layer.getFeatures():
                    f_area = feature.geometry().area() * (111000 ** 2)
                    if f_area > (thickness * 2):
                        stats["fit"] += 1
                        stats["cult_area"] += f_area
                        feature.setAttributes([stats["fit"], round(f_area, 2)])
                        res_layer.updateFeature(feature)
                    else:
                        res_layer.deleteFeature(feature.id())
                res_layer.commitChanges()

                aisle_area = total_area_m2 - stats["cult_area"]
                efficiency = (stats["cult_area"] / total_area_m2) * 100

                # Renderizado de la malla de franjas
                mesh_props = {
                    'color': '0,255,0,255',
                    'outline_color': '0,150,0,255',
                    'outline_width': '0.4',
                    'style': 'cross'
                }
                mesh_sym = QgsFillSymbol.createSimple(mesh_props)
                res_layer.setRenderer(QgsSingleSymbolRenderer(mesh_sym))
                QgsProject.instance().addMapLayer(res_layer)

                # Líneas guía GPS
                gps_clip = processing.run("native:clip", {
                    'INPUT': capa_lines,
                    'OVERLAY': layer,
                    'OUTPUT': 'memory:GPS_Lines'
                })['OUTPUT']
                gps_sym = QgsLineSymbol.createSimple({
                    'color': '255,165,0,255',
                    'width': '1.2',
                    'line_style': 'dash'
                })
                gps_clip.setRenderer(QgsSingleSymbolRenderer(gps_sym))
                QgsProject.instance().addMapLayer(gps_clip)

                print("\n" + "═" * 45)
                print(f"║ {'TECHNICAL REPORT: STRIPS':^41} ║")
                print("═" * 45)
                print(f"  Total Plot Area:   {total_area_m2:10.2f} m²")
                print(f"  Cultivation Area:  {stats['cult_area']:10.2f} m²")
                print(f"  Aisle Area:        {aisle_area:10.2f} m²")
                print(f"  Efficiency:        {efficiency:10.2f} %")
                print(f"  Total Rows:        {stats['fit']:>10}")
                print("═" * 45)

            else:
                # Lógica de Mosaicos (Fractal de Hilbert)
                stats = {
                    "optimal": 0,    # Mosaicos verdes (>99.9%)
                    "suitable": 0,   # Mosaicos amarillos (>= pct_threshold)
                    "discard": 0,    # Mosaicos rojos (< pct_threshold)
                    "util_area": 0.0 # Área acumulada útil
                }
                
                n_grid = 2 ** density
                step = thickness + aisle
                r_deg = (thickness / 2) / 111000.0
                area_ref = (thickness ** 2 if shape == "Cuadrado" else
                            (math.pi * (thickness / 2) ** 2))

                capa_t = QgsVectorLayer(
                    "Polygon?crs=EPSG:4326", "Layout_Mosaics", "memory"
                )
                capa_c = QgsVectorLayer(
                    "Point?crs=EPSG:4326", "Unit_Centers", "memory"
                )

                for c in [capa_t, capa_c]:
                    c.dataProvider().addAttributes([
                        QgsField("Unit_ID", QVariant.Int),
                        QgsField("status", QVariant.String),
                        QgsField("pct_area", QVariant.Double)
                    ])
                    c.updateFields()

                path_pts = []
                for d in range(n_grid * n_grid):
                    hx, hy = self.d2xy(n_grid, d)
                    ox = (hx - n_grid / 2) * step
                    oy = (hy - n_grid / 2) * step
                    p_c = self.rotate_point(
                        pivot.x() + ox / 111000.0,
                        pivot.y() + oy / 111000.0,
                        pivot.x(), pivot.y(), angle
                    )
                    u_geom = self.create_geometry(p_c, shape, r_deg, angle)

                    if u_geom.intersects(geom_parcel):
                        inter = u_geom.intersection(geom_parcel)
                        f_area = inter.area() * (111000 ** 2)
                        pct = (f_area / area_ref) * 100
                        
                        # Clasificación según el semáforo de porcentaje
                        if pct >= 99.9:
                            status = "Optimal (Green)"
                            stats["optimal"] += 1
                        elif pct >= pct_threshold:
                            status = "Suitable (Yellow)"
                            stats["suitable"] += 1
                        else:
                            status = "Discarded (Red)"
                            stats["discard"] += 1

                        u_id = None
                        if pct >= pct_threshold:
                            stats["util_area"] += f_area
                            u_id = stats["optimal"] + stats["suitable"]
                            path_pts.append(p_c)
                            if draw_centers:
                                fc = QgsFeature()
                                fc.setGeometry(QgsGeometry.fromPointXY(p_c))
                                fc.setAttributes([u_id, status, round(pct, 1)])
                                capa_c.dataProvider().addFeature(fc)

                        f = QgsFeature()
                        f.setGeometry(inter)
                        f.setAttributes([u_id, status, round(pct, 1)])
                        capa_t.dataProvider().addFeature(f)

                if draw_path and len(path_pts) > 1:
                    capa_r = QgsVectorLayer(
                        "LineString?crs=EPSG:4326", "Hilbert_Path", "memory"
                    )
                    fr = QgsFeature()
                    fr.setGeometry(QgsGeometry.fromPolylineXY(path_pts))
                    capa_r.dataProvider().addFeature(fr)
                    capa_r.setRenderer(QgsSingleSymbolRenderer(
                        QgsLineSymbol.createSimple({
                            'color': '255,120,0,255', 'width': '1.0'
                        })
                    ))
                    QgsProject.instance().addMapLayer(capa_r)

                self.apply_status_style(capa_t)
                self.create_label_layer(capa_t, "Unit_ID", "Labels_Mosaics")
                QgsProject.instance().addMapLayer(capa_t)
                if draw_centers:
                    QgsProject.instance().addMapLayer(capa_c)
                if draw_coords:
                    self.create_coord_layer(capa_c)

                # Reporte técnico completo para Mosaicos
                total_units = stats["optimal"] + stats["suitable"]
                unused_area_m2 = total_area_m2 - stats["util_area"]
                efficiency = (stats["util_area"] / total_area_m2) * 100

                print("\n" + "═" * 45)
                print(f"║ {'TECHNICAL REPORT: MOSAICS':^41} ║")
                print("═" * 45)
                print(f"  Total Plot Area:   {total_area_m2:10.2f} m²")
                print(f"  Cultivation Area:  {stats['util_area']:10.2f} m²")
                print(f"  Unused/Aisle Area: {unused_area_m2:10.2f} m²")
                print(f"  Efficiency:        {efficiency:10.2f} %")
                print("─" * 45)
                print(f"  Optimal Units (Green):   {stats['optimal']:>6}")
                print(f"  Suitable Units (Yellow):  {stats['suitable']:>6}")
                print(f"  Discarded Units (Red):   {stats['discard']:>6}")
                print(f"  Total Valid Units:       {total_units:>6}")
                print("═" * 45)

    def create_label_layer(self, source_layer, field_id, layer_name):
        """Creates labeling layer."""
        lbl_layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        lbl_layer.dataProvider().addAttributes([
            QgsField("Label_ID", QVariant.String)
        ])
        lbl_layer.updateFields()

        feats = []
        for feat in source_layer.getFeatures():
            val = feat[field_id]
            if val is not None and val != NULL:
                f = QgsFeature()
                f.setGeometry(feat.geometry().centroid())
                f.setAttributes([str(val)])
                feats.append(f)
        lbl_layer.dataProvider().addFeatures(feats)

        settings = QgsPalLayerSettings()
        settings.fieldName = "Label_ID"
        settings.placement = QgsPalLayerSettings.AroundPoint
        txt = QgsTextFormat()
        txt.setSize(12)
        txt.setColor(QColor("black"))
        buff = QgsTextBufferSettings()
        buff.setEnabled(True)
        buff.setSize(1)
        txt.setBuffer(buff)
        settings.setFormat(txt)
        lbl_layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        lbl_layer.setLabelsEnabled(True)
        lbl_layer.renderer().symbol().setSize(0)
        QgsProject.instance().addMapLayer(lbl_layer)

    def apply_status_style(self, layer):
        """Applies semaphore style."""
        props = {'outline_color': 'white', 'style': 'solid'}
        cats = [
            QgsRendererCategory(
                "Optimal (Green)",
                QgsFillSymbol.createSimple({'color': '76,175,80,150', **props}),
                "Optimal (>99%)"
            ),
            QgsRendererCategory(
                "Suitable (Yellow)",
                QgsFillSymbol.createSimple(
                    {'color': '255,235,59,150', **props}
                ),
                "Suitable (Cut)"
            ),
            QgsRendererCategory(
                "Discarded (Red)",
                QgsFillSymbol.createSimple({'color': '244,67,54,150', **props}),
                "Discarded"
            )
        ]
        layer.setRenderer(QgsCategorizedSymbolRenderer("status", cats))
        layer.triggerRepaint()

    def create_coord_layer(self, centers_layer):
        """Generates coordinate labels."""
        c_layer = QgsVectorLayer("Point?crs=EPSG:4326", "Coord_Layer", "memory")
        c_layer.dataProvider().addAttributes([
            QgsField("LAT_Y", QVariant.Double),
            QgsField("LON_X", QVariant.Double)
        ])
        c_layer.updateFields()

        feats = []
        for feat in centers_layer.getFeatures():
            geom = feat.geometry()
            p = geom.asPoint()
            f = QgsFeature()
            f.setGeometry(geom)
            f.setAttributes([round(p.y(), 8), round(p.x(), 8)])
            feats.append(f)
        c_layer.dataProvider().addFeatures(feats)

        settings = QgsPalLayerSettings()
        settings.fieldName = (
            "to_dms($y, 'y', 2) || ' ' || to_dms($x, 'x', 2) + "
            "'\nDD: ' + format_number($y, 6) + ', ' + format_number($x, 6)"
        )
        settings.isExpression = True
        settings.placement = QgsPalLayerSettings.AroundPoint
        settings.scaleVisibility = True
        settings.minimumScale = 2500

        txt = QgsTextFormat()
        txt.setSize(12)
        txt.setColor(QColor("black"))
        buff = QgsTextBufferSettings()
        buff.setEnabled(True)
        buff.setSize(1.0)
        buff.setColor(QColor("white"))
        txt.setBuffer(buff)
        settings.setFormat(txt)

        c_layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        c_layer.setLabelsEnabled(True)
        c_layer.renderer().symbol().setSize(0)
        QgsProject.instance().addMapLayer(c_layer)