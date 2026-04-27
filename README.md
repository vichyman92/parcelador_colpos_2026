Parcelador_COLPOS (v1.0)
Developed by: Manuel Vichique Alegría & Gemini AI

Institution: Colegio de Postgraduados (COLPOS), México.

*-*-*-*-*-*-*-*-*-* *-*-*-*-*-*-*-*-*-* Technical Notes *-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-*

*Accuracy & Coordinate Systems-The plugin performs calculations based on a Euclidean (Cartesian) plane. To maintain consistency across different regions, the following logic is applied:
1-Spherical Approximation: The algorithm uses a constant factor ($1^\circ \approx 111,000$ meters).
2-Precision: Cartesian Measurement: Distances and areas are mathematically exact within the plugin's internal logic.
3-Geographic Measurement: In EPSG:4326, users may notice slight variations in real-world metric distances due to   the  Earth's curvature (longitudinal convergence).
4-Recommendation: For projects requiring sub-centimetric precision in field implementation (e.g., GPS-guided     planting), it is highly recommended to reproject the input layers to a local UTM Zone (Projected Coordinate System) before running the tool.
5-To ensure accuracy in area calculations and plot delimitation, the following is recommended:
6-Geometry: Polygon layers.

Coordinate Reference System (CRS): The plugin has been successfully tested using EPSG:4326.
Field of Application: precision agriculture, agricultural managment, crop monitoring.

*-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-**-*-*-*-*-*-*-*-*-*
1. General Description
Parcelador_COLPOS is a QGIS plugin designed for the spatial optimization of agricultural production units. Its main objective is to facilitate the design of monitoring routes and plot delimitation based on criteria relevant to the technicians and producers who use it.

This plugin is a core component of the doctoral research: "SYSTEM FOR AUTOMATED MONITORING AND SELECTIVITY OF CHAYOTE [Sechium Edule (jacq) sw.] DURING THE CROP CYCLE."



2. Key Features
Strip Mode (Franjas): Automatic generation of optimized crop rows based on strip thickness and transit aisle width.

Mosaic Mode (Hilbert): Implementation of the Hilbert Curve to create sampling mosaics. This algorithm ensures that production units are traversed sequentially and efficiently, making it ideal for autonomous robots and other logistical activities.

Variable Geometry: Support for units in the shape of squares, triangles, or circles, adapting to different types of trellising and crop structures.

GPS Export: Generation of an independent coordinate layer (LAT/LON) with 8-decimal precision, ready to be used on other platforms and hardware.

Efficiency Analysis: Automatic console reporting on the useful area achieved and the efficiency percentage relative to the original polygon.

3. Installation
Download the .zip file from the repository.

In QGIS, go to Plugins > Manage and Install Plugins.

Select Install from ZIP and choose the downloaded file.

4. How to Use
Select a polygon layer representing your plot.

Click the Parcelador_COLPOS icon in the toolbar.

Configure the design parameters (meters, aisles, rotation angle).

Enable the "Hilbert Path" or "Coordinate Layer" options according to your visualization needs.

Click OK and review the detailed report in the Message Bar and the Python Console.

5. Technical Requirements
QGIS: 3.x (Tested on 3.44 LTR).

Python: 3.12+

Dependencies: qgis.core, qgis.gui, qgis.utils.

This software is distributed under the GNU General Public License (GPL) v2 or later.


***********----------------*****************------------------***********----------------*****************------------
Parcelador_COLPOS (v1.0)
Desarrollado por: Manuel Vichique Alegría & Gemini IA

Institución: Colegio de Postgraduados (COLPOS), México.

Este complemento realiza cálculos basados en un plano euclidiano (cartesiano). Para mantener la consistencia en diferentes regiones, se aplica la siguiente lógica:
Aproximación Esférica: El algoritmo utiliza un factor constante ($1^\circ \approx 111,000$ metros).Precisión:Medición Cartesiana: Las distancias y áreas son matemáticamente exactas dentro de la lógica interna del plugin.
Medición Geográfica: En el sistema EPSG:4326, los usuarios pueden notar ligeras variaciones en las distancias métricas reales debido a la curvatura de la Tierra (convergencia de meridianos).
Recomendación: Para proyectos que requieran precisión sub-centimétrica en la implementación de campo (ej. siembra guiada por GPS), se recomienda encarecidamente reproyectar las capas de entrada a una zona UTM local (Sistema de Coordenadas Proyectadas) antes de ejecutar la herramienta.
Requisitos de los datos: Para asegurar la precisión en el cálculo de áreas y la delimitación de parcelas, se recomienda:
Geometría: Capas de tipo Polígono.Sistema de Referencia (SRC): El plugin ha sido probado con éxito utilizando EPSG:4326.Campos de Aplicación: Agricultura de Precisión, Robótica Agrícola, Monitoreo de Cultivos.

1. Descripción General
Parcelador_COLPOS es un complemento de QGIS diseñado para la optimización espacial de unidades de producción agrícola. Su objetivo principal es facilitar el diseño de recorridos de monitoreo y la delimitación de parcelas bajo criterios que sean de interés para los técnicos y productores que la usen

Este plugin es parte de la investigación doctoral: "SISTEMA PARA MONITOREO Y SELECTIVIDAD AUTOMATIZADA DE CHAYOTE [Sechium Edule (jacq) sw.] DURANTE EL CICLO DE CULTIVO".

*-*-*-*-*-Requisitos de los datos de entrada*-*-*-*-*-
Para asegurar la precisión en el cálculo de áreas y la delimitación de las parcelas, se recomienda:

Geometría: Capas de tipo Polígono (Polygon).
Sistema de Referencia (SRC): * El plugin fue probado exitosamente en EPSG:4326.

Nota técnica: Para cálculos de precisión métrica (distancias reales en campo), se recomienda proyectar la capa a la zona UTM correspondiente a tu ubicación (ej. WGS 84 / UTM zone 14N para gran parte de México) antes de ejecutar el proceso.

2. Funcionalidades Clave
Modo Franjas: Generación automática de surcos de cultivo optimizados según el grosor de la franja y el pasillo de tránsito.

Modo Mosaicos (Hilbert): Implementación de la Curva de Hilbert para crear mosaicos de muestreo. Este algoritmo garantiza que las unidades de producción sean recorridas de manera secuencial y eficiente, ideal para robots autónomos u otras actividades.

Geometría Variable: Soporte para unidades en forma de cuadrados, triángulos o círculos, adaptándose a diferentes tipos de tutoreo .

Exportación GPS: Generación de una capa independiente de coordenadas (LAT/LON) con precisión de 8 decimales, lista para ser utilizada en otras plataformas.

Análisis de Eficiencia: Reporte automático en consola sobre el área útil lograda y el porcentaje de eficiencia respecto al polígono original.

3. Instalación
Descargue el archivo .zip del repositorio.

En QGIS, vaya a Complementos > Administrar e instalar complementos.

Seleccione Instalar a partir de ZIP y elija el archivo descargado.

4. Cómo usar
Seleccione una capa de polígono que represente su parcela.

Abra el icono del Parcelador_COLPOS en la barra de herramientas.

Configure los parámetros de diseño (metros, pasillos, ángulo de rotación).

Active las opciones de "Ruta de Hilbert" o "Capa de Coordenadas" según sus necesidades de visualización.

Haga clic en OK y revise el reporte detallado en el panel de mensajes y en la consola de Python.

5. Requisitos Técnicos
QGIS: 3.x (Probado en 3.44 LTR).

Python: 3.12+

Dependencias: qgis.core, qgis.gui, qgis.utils.

Este software se distribuye bajo la licencia GNU General Public License (GPL) v2 o posterior.
