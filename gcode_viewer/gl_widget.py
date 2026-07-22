from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, QPoint, QTimer, QThread, Signal
from OpenGL.GL import (
    glEnable, glDisable, glClear, glClearColor, glLoadIdentity,
    glMatrixMode, glViewport, glBegin, glEnd, glVertex3f, glColor3f,
    glLineWidth, glTranslatef, glRotatef, glScalef, glPushMatrix, glPopMatrix,
    GL_DEPTH_TEST, GL_LINES, GL_PROJECTION, GL_MODELVIEW,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    glFrustum,
    glLightfv, glLightf, glMaterialfv, glNormal3f,
    GL_LIGHTING, GL_NORMALIZE, GL_LIGHT0, GL_LIGHT1, GL_LIGHT2, GL_LIGHT3, GL_LIGHT4, GL_FRONT,
    GL_POSITION, GL_AMBIENT, GL_DIFFUSE, GL_SPECULAR, GL_SHININESS,
    GL_SPOT_DIRECTION, GL_SPOT_CUTOFF, GL_SPOT_EXPONENT,
    glShadeModel, GL_SMOOTH, GL_QUADS,
    glGenBuffers, glBindBuffer, glBufferData, glBufferSubData, glDeleteBuffers,
    GL_ARRAY_BUFFER, GL_STATIC_DRAW,
    glEnableClientState, glDisableClientState,
    glVertexPointer, glNormalPointer, glDrawArrays, GL_FLOAT,
    GL_VERTEX_ARRAY, GL_NORMAL_ARRAY
)
import numpy as np
import math
import time


class VBOBuilder(QThread):
    finished = Signal(object, object, int, object, object, int)
    progress = Signal(int)

    def __init__(self, model, visible_layers, show_travel, tube_radius, tube_sides):
        super().__init__()
        self.model = model
        self.visible_layers = visible_layers
        self.show_travel = show_travel
        self.tube_radius = tube_radius
        self.tube_sides = tube_sides

    def run(self):
        start_time = time.time()

        if not self.model:
            self.finished.emit(None, None, 0, None, None, 0)
            return

        radius = self.tube_radius
        num_sides = self.tube_sides

        cos_table = np.cos(2 * np.pi * np.arange(num_sides) / num_sides)
        sin_table = np.sin(2 * np.pi * np.arange(num_sides) / num_sides)

        extrude_segments = []
        travel_segments = []

        total_segments = 0
        processed = 0

        for layer_index, layer in enumerate(self.model.layers):
            if layer_index not in self.visible_layers:
                continue

            for segment in layer.segments:
                total_segments += 1
                if not self.show_travel and not segment.extruding:
                    continue

                if segment.extruding:
                    extrude_segments.append((segment.x1, segment.y1, segment.z1,
                                            segment.x2, segment.y2, segment.z2))
                else:
                    travel_segments.append((segment.x1, segment.y1, segment.z1,
                                           segment.x2, segment.y2, segment.z2))

        self.progress.emit(20)

        extrude_vertices, extrude_normals, extrude_count = self._build_group(
            extrude_segments, radius, num_sides, cos_table, sin_table)

        self.progress.emit(60)

        travel_vertices, travel_normals, travel_count = self._build_group(
            travel_segments, radius, num_sides, cos_table, sin_table)

        self.progress.emit(100)

        elapsed = time.time() - start_time

        self.finished.emit(
            extrude_vertices, extrude_normals, extrude_count,
            travel_vertices, travel_normals, travel_count
        )

    def _build_group(self, segments, radius, num_sides, cos_table, sin_table):
        if not segments:
            return None, None, 0

        segments = np.array(segments, dtype=np.float32)
        x1, y1, z1 = segments[:, 0], segments[:, 1], segments[:, 2]
        x2, y2, z2 = segments[:, 3], segments[:, 4], segments[:, 5]

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        length = np.sqrt(dx**2 + dy**2 + dz**2)

        mask = length >= 0.0001
        if not np.any(mask):
            return None, None, 0

        x1, y1, z1 = x1[mask], y1[mask], z1[mask]
        x2, y2, z2 = x2[mask], y2[mask], z2[mask]
        dx, dy, dz = dx[mask], dy[mask], dz[mask]
        length = length[mask]

        dx /= length
        dy /= length
        dz /= length

        abs_dx = np.abs(dx)
        abs_dy = np.abs(dy)
        mask_x = abs_dx > abs_dy

        s = np.where(mask_x, np.sqrt(dx**2 + dz**2), np.sqrt(dy**2 + dz**2))
        tx = np.where(mask_x, dz / s, 0.0)
        ty = np.where(mask_x, 0.0, dz / s)
        tz = np.where(mask_x, -dx / s, -dy / s)

        bx = dy * tz - dz * ty
        by = dz * tx - dx * tz
        bz = dx * ty - dy * tx

        num_seg = len(x1)
        num_verts = num_seg * num_sides * 4

        vertices = np.zeros((num_verts, 3), dtype=np.float32)
        normals = np.zeros((num_verts, 3), dtype=np.float32)

        idx = 0
        for i in range(num_sides):
            j = (i + 1) % num_sides
            cx1, cy1 = cos_table[i], sin_table[i]
            cx2, cy2 = cos_table[j], sin_table[j]

            nx1 = cx1 * bx + cy1 * tx
            ny1 = cx1 * by + cy1 * ty
            nz1 = cx1 * bz + cy1 * tz

            nx2 = cx2 * bx + cy2 * tx
            ny2 = cx2 * by + cy2 * ty
            nz2 = cx2 * bz + cy2 * tz

            v1x = x1 + radius * nx1
            v1y = y1 + radius * ny1
            v1z = z1 + radius * nz1

            v2x = x2 + radius * nx1
            v2y = y2 + radius * ny1
            v2z = z2 + radius * nz1

            v3x = x2 + radius * nx2
            v3y = y2 + radius * ny2
            v3z = z2 + radius * nz2

            v4x = x1 + radius * nx2
            v4y = y1 + radius * ny2
            v4z = z1 + radius * nz2

            for seg in range(num_seg):
                vertices[idx] = [v1x[seg], v1y[seg], v1z[seg]]
                normals[idx] = [nx1[seg], ny1[seg], nz1[seg]]
                idx += 1

                vertices[idx] = [v2x[seg], v2y[seg], v2z[seg]]
                normals[idx] = [nx1[seg], ny1[seg], nz1[seg]]
                idx += 1

                vertices[idx] = [v3x[seg], v3y[seg], v3z[seg]]
                normals[idx] = [nx2[seg], ny2[seg], nz2[seg]]
                idx += 1

                vertices[idx] = [v4x[seg], v4y[seg], v4z[seg]]
                normals[idx] = [nx2[seg], ny2[seg], nz2[seg]]
                idx += 1

        return vertices, normals, num_verts


class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gcode_model = None
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.zoom = 1.0
        self.last_pos = QPoint()
        self.show_axis = True
        self.show_grid = True
        self.show_travel = True
        self.visible_layers = set()
        self.grid_size = 50
        self.grid_divisions = 10
        self.use_lighting = True
        self.use_tubes = True
        self.ambient_intensity = 0.3
        self.spotlight_intensity = 0.8
        self.tube_radius = 0.15
        self.tube_sides = 8

        self._vbo_initialized = False
        self._extrude_vbo = 0
        self._extrude_vertices = None
        self._extrude_normals = None
        self._extrude_count = 0

        self._travel_vbo = 0
        self._travel_vertices = None
        self._travel_normals = None
        self._travel_count = 0

        self._vbo_builder = None

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(16)
        self._update_timer.timeout.connect(self._do_update)
        self._update_pending = False

    def set_model(self, model):
        self.gcode_model = model
        self.visible_layers = set(range(model.get_layer_count())) if model else set()
        self._schedule_vbo_build()
        self.update()

    def set_visible_layers(self, layers):
        self.visible_layers = layers
        self._schedule_vbo_build()
        self.update()

    def reset_view(self):
        self.rotation_x = 0.0
        self.rotation_y = 0.0
        self.zoom = 1.0
        self.update()

    def set_view_preset(self, preset):
        presets = {
            'top': (0.0, 0.0),
            'front': (-90.0, 0.0),
            'side': (0.0, -90.0),
            'isometric': (-35.26, -45.0),
        }
        if preset in presets:
            self.rotation_x, self.rotation_y = presets[preset]
            self.zoom = 1.0
            self.update()

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.08, 0.08, 0.12, 1.0)
        glShadeModel(GL_SMOOTH)

        glEnable(GL_LIGHTING)
        glEnable(GL_NORMALIZE)

        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.5, 0.5, 0.5, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT0, GL_POSITION, [50.0, 50.0, 150.0, 1.0])
        glEnable(GL_LIGHT0)

        glLightfv(GL_LIGHT1, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1.0, 0.9, 0.8, 1.0])
        glLightfv(GL_LIGHT1, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT1, GL_POSITION, [-80.0, 60.0, 100.0, 1.0])
        glLightfv(GL_LIGHT1, GL_SPOT_DIRECTION, [1.0, -0.5, -1.0])
        glLightf(GL_LIGHT1, GL_SPOT_CUTOFF, 45.0)
        glLightf(GL_LIGHT1, GL_SPOT_EXPONENT, 15.0)
        glEnable(GL_LIGHT1)

        glLightfv(GL_LIGHT2, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glLightfv(GL_LIGHT2, GL_DIFFUSE, [0.9, 0.95, 1.0, 1.0])
        glLightfv(GL_LIGHT2, GL_SPECULAR, [0.8, 0.8, 1.0, 1.0])
        glLightfv(GL_LIGHT2, GL_POSITION, [80.0, -40.0, 120.0, 1.0])
        glEnable(GL_LIGHT2)

        glLightfv(GL_LIGHT3, GL_AMBIENT, [0.15, 0.15, 0.15, 1.0])
        glLightfv(GL_LIGHT3, GL_DIFFUSE, [0.95, 0.9, 0.85, 1.0])
        glLightfv(GL_LIGHT3, GL_SPECULAR, [0.9, 0.9, 0.9, 1.0])
        glLightfv(GL_LIGHT3, GL_POSITION, [-60.0, -80.0, 100.0, 1.0])
        glEnable(GL_LIGHT3)

        glLightfv(GL_LIGHT4, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glLightfv(GL_LIGHT4, GL_DIFFUSE, [0.8, 0.9, 1.0, 1.0])
        glLightfv(GL_LIGHT4, GL_SPECULAR, [0.7, 0.8, 0.9, 1.0])
        glLightfv(GL_LIGHT4, GL_POSITION, [0.0, 0.0, 200.0, 1.0])
        glEnable(GL_LIGHT4)

        self._extrude_vbo = glGenBuffers(1)
        self._travel_vbo = glGenBuffers(1)
        self._vbo_initialized = True

    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = width / height if height > 0 else 1.0
        glFrustum(-aspect, aspect, -1.0, 1.0, 1.0, 2000.0)
        glMatrixMode(GL_MODELVIEW)

    def update_lighting(self):
        glLightfv(GL_LIGHT0, GL_AMBIENT, [self.ambient_intensity]*3 + [1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [self.ambient_intensity*2]*3 + [1.0])
        
        spot_intensity = self.spotlight_intensity
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [spot_intensity]*3 + [1.0])
        glLightfv(GL_LIGHT1, GL_SPECULAR, [spot_intensity]*3 + [1.0])
        
        if self.use_lighting:
            glEnable(GL_LIGHTING)
        else:
            glDisable(GL_LIGHTING)
        self.update()

    def _schedule_vbo_build(self):
        if self._vbo_builder and self._vbo_builder.isRunning():
            self._vbo_builder.quit()
            self._vbo_builder.wait()

        if not self.gcode_model or not self.use_tubes:
            self._extrude_count = 0
            self._travel_count = 0
            return

        self._vbo_builder = VBOBuilder(
            self.gcode_model,
            self.visible_layers,
            self.show_travel,
            self.tube_radius,
            self.tube_sides
        )
        self._vbo_builder.finished.connect(self._on_vbo_build_finished)
        self._vbo_builder.start()

    def _on_vbo_build_finished(self, extrude_vertices, extrude_normals, extrude_count,
                                travel_vertices, travel_normals, travel_count):
        self._extrude_vertices = extrude_vertices
        self._extrude_normals = extrude_normals
        self._extrude_count = extrude_count

        self._travel_vertices = travel_vertices
        self._travel_normals = travel_normals
        self._travel_count = travel_count

        if self._vbo_initialized:
            if self._extrude_vertices is not None:
                glBindBuffer(GL_ARRAY_BUFFER, self._extrude_vbo)
                glBufferData(GL_ARRAY_BUFFER,
                            self._extrude_vertices.nbytes + self._extrude_normals.nbytes,
                            None, GL_STATIC_DRAW)
                glBufferSubData(GL_ARRAY_BUFFER, 0, self._extrude_vertices.nbytes, self._extrude_vertices)
                glBufferSubData(GL_ARRAY_BUFFER, self._extrude_vertices.nbytes,
                                self._extrude_normals.nbytes, self._extrude_normals)
                glBindBuffer(GL_ARRAY_BUFFER, 0)

            if self._travel_vertices is not None:
                glBindBuffer(GL_ARRAY_BUFFER, self._travel_vbo)
                glBufferData(GL_ARRAY_BUFFER,
                            self._travel_vertices.nbytes + self._travel_normals.nbytes,
                            None, GL_STATIC_DRAW)
                glBufferSubData(GL_ARRAY_BUFFER, 0, self._travel_vertices.nbytes, self._travel_vertices)
                glBufferSubData(GL_ARRAY_BUFFER, self._travel_vertices.nbytes,
                                self._travel_normals.nbytes, self._travel_normals)
                glBindBuffer(GL_ARRAY_BUFFER, 0)

        self.update()

    def update(self):
        if not self._update_timer.isActive():
            self._update_pending = True
            self._update_timer.start()

    def _do_update(self):
        if self._update_pending:
            self._update_pending = False
            self._update_timer.stop()
            super().update()

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        glTranslatef(0.0, 0.0, -300.0 * self.zoom)

        glRotatef(self.rotation_x, 1.0, 0.0, 0.0)
        glRotatef(self.rotation_y, 0.0, 1.0, 0.0)

        if self.show_grid:
            self._draw_grid()

        if self.show_axis:
            self._draw_axis()

        if self.gcode_model:
            self._draw_model()

    def _draw_grid(self):
        grid_center = self.gcode_model.center if self.gcode_model else {'x': 0, 'y': 0}
        
        glDisable(GL_LIGHTING)
        glLineWidth(1.0)
        glColor3f(0.3, 0.3, 0.4)

        half_size = self.grid_size / 2
        step = self.grid_size / self.grid_divisions

        glBegin(GL_LINES)
        for i in range(-self.grid_divisions, self.grid_divisions + 1):
            x = grid_center['x'] + i * step
            glVertex3f(x, grid_center['y'] - half_size, 0)
            glVertex3f(x, grid_center['y'] + half_size, 0)

            y = grid_center['y'] + i * step
            glVertex3f(grid_center['x'] - half_size, y, 0)
            glVertex3f(grid_center['x'] + half_size, y, 0)
        glEnd()

        glLineWidth(2.0)
        glColor3f(0.5, 0.5, 0.6)
        glBegin(GL_LINES)
        glVertex3f(grid_center['x'] - half_size, grid_center['y'], 0)
        glVertex3f(grid_center['x'] + half_size, grid_center['y'], 0)
        glVertex3f(grid_center['x'], grid_center['y'] - half_size, 0)
        glVertex3f(grid_center['x'], grid_center['y'] + half_size, 0)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_axis(self):
        axis_length = self.grid_size / 2

        glPushMatrix()

        if self.gcode_model and self.gcode_model.center:
            glTranslatef(self.gcode_model.center['x'], self.gcode_model.center['y'], 0)

        glDisable(GL_LIGHTING)
        glLineWidth(3.0)

        glColor3f(1.0, 0.0, 0.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(axis_length, 0, 0)
        glEnd()

        glColor3f(0.0, 1.0, 0.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, axis_length, 0)
        glEnd()

        glColor3f(0.0, 0.0, 1.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, axis_length)
        glEnd()
        glEnable(GL_LIGHTING)

        glPopMatrix()

    def _draw_model(self):
        model = self.gcode_model
        glPushMatrix()

        glScalef(model.scale, model.scale, model.scale)

        if model.center:
            glTranslatef(
                -model.center['x'],
                -model.center['y'],
                -model.center['z']
            )

        if self.use_tubes and self.use_lighting:
            self._draw_model_tubes_vbo()
        else:
            self._draw_model_lines()

        glPopMatrix()

    def _draw_model_tubes_vbo(self):
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        if self._extrude_count > 0 and self._extrude_vertices is not None:
            glMaterialfv(GL_FRONT, GL_AMBIENT, [0.5, 0.5, 0.5, 1.0])
            glMaterialfv(GL_FRONT, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
            glMaterialfv(GL_FRONT, GL_SPECULAR, [0.9, 0.9, 0.9, 1.0])
            glMaterialfv(GL_FRONT, GL_SHININESS, [100.0])

            glBindBuffer(GL_ARRAY_BUFFER, self._extrude_vbo)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glNormalPointer(GL_FLOAT, 0, self._extrude_vertices.nbytes)
            glDrawArrays(GL_QUADS, 0, self._extrude_count)

        if self.show_travel and self._travel_count > 0 and self._travel_vertices is not None:
            glMaterialfv(GL_FRONT, GL_AMBIENT, [0.3, 0.3, 0.4, 1.0])
            glMaterialfv(GL_FRONT, GL_DIFFUSE, [0.5, 0.5, 0.8, 1.0])
            glMaterialfv(GL_FRONT, GL_SPECULAR, [0.4, 0.4, 0.7, 1.0])
            glMaterialfv(GL_FRONT, GL_SHININESS, [30.0])

            glBindBuffer(GL_ARRAY_BUFFER, self._travel_vbo)
            glVertexPointer(3, GL_FLOAT, 0, None)
            glNormalPointer(GL_FLOAT, 0, self._travel_vertices.nbytes)
            glDrawArrays(GL_QUADS, 0, self._travel_count)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)

    def _draw_model_lines(self):
        glDisable(GL_LIGHTING)

        for layer_index, layer in enumerate(self.gcode_model.layers):
            if layer_index not in self.visible_layers:
                continue

            for segment in layer.segments:
                if not self.show_travel and not segment.extruding:
                    continue

                r, g, b = segment.color

                if segment.extruding:
                    glColor3f(r, g, b)
                    glLineWidth(2.0)
                else:
                    glColor3f(r * 0.5, g * 0.5, b * 0.5)
                    glLineWidth(1.0)

                glBegin(GL_LINES)
                glVertex3f(segment.x1, segment.y1, segment.z1)
                glVertex3f(segment.x2, segment.y2, segment.z2)
                glEnd()

        glEnable(GL_LIGHTING)

    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()

        if event.buttons() & Qt.LeftButton:
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.5
            self.rotation_x = max(-90.0, min(90.0, self.rotation_x))
            self.update()
        elif event.buttons() & Qt.RightButton:
            self.zoom += dy * 0.001 * self.zoom
            self.zoom = max(0.1, min(10.0, self.zoom))
            self.update()

        self.last_pos = event.pos()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom = min(self.zoom * 1.1, 10.0)
        else:
            self.zoom = max(self.zoom / 1.1, 0.1)
        self.update()