import math
from .gcode_parser import GCodeParser


class Segment:
    def __init__(self, x1, y1, z1, x2, y2, z2, extruding, color, feed_rate=0):
        self.x1 = x1
        self.y1 = y1
        self.z1 = z1
        self.x2 = x2
        self.y2 = y2
        self.z2 = z2
        self.extruding = extruding
        self.color = color
        self.feed_rate = feed_rate


class Layer:
    def __init__(self, layer_index, z):
        self.layer_index = layer_index
        self.z = z
        self.segments = []
        self.extruding_segments = 0
        self.travel_segments = 0

    def add_segment(self, segment):
        self.segments.append(segment)
        if segment.extruding:
            self.extruding_segments += 1
        else:
            self.travel_segments += 1


class GCodeModel:
    def __init__(self):
        self.layers = []
        self.bbox = {
            'min': {'x': 100000, 'y': 100000, 'z': 100000},
            'max': {'x': -100000, 'y': -100000, 'z': -100000}
        }
        self.center = None
        self.scale = 3.0
        self.total_extrusion = 0
        self.total_travel = 0
        self.max_feed_rate = 0
        self.min_feed_rate = float('inf')

    def _update_bbox(self, x, y, z):
        self.bbox['min']['x'] = min(self.bbox['min']['x'], x)
        self.bbox['min']['y'] = min(self.bbox['min']['y'], y)
        self.bbox['min']['z'] = min(self.bbox['min']['z'], z)
        self.bbox['max']['x'] = max(self.bbox['max']['x'], x)
        self.bbox['max']['y'] = max(self.bbox['max']['y'], y)
        self.bbox['max']['z'] = max(self.bbox['max']['z'], z)

    def load_from_gcode(self, gcode):
        self.layers = []
        self.total_extrusion = 0
        self.total_travel = 0
        self.max_feed_rate = 0
        self.min_feed_rate = float('inf')

        last_line = {'x': 0, 'y': 0, 'z': 0, 'e': 0, 'f': 0}
        current_layer = None
        self._relative = False
        self._e_relative = False

        def delta(v1, v2):
            return v2 if self._relative else v2 - v1

        def absolute(v1, v2):
            return v1 + v2 if self._relative else v2

        def delta_e(v1, v2):
            return v2 if self._e_relative else v2 - v1

        def absolute_e(v1, v2):
            return v1 + v2 if self._e_relative else v2

        def new_layer(z):
            nonlocal current_layer
            layer_index = len(self.layers)
            current_layer = Layer(layer_index, z)
            self.layers.append(current_layer)

        def add_segment(p1, p2, extruding, feed_rate):
            nonlocal current_layer
            if extruding and (current_layer is None or p2['z'] != current_layer.z):
                new_layer(p2['z'])

            if current_layer is None:
                new_layer(p2['z'])

            color = (1.0, 1.0, 1.0) if extruding else (0.4, 0.4, 0.8)
            segment = Segment(
                p1['x'], p1['y'], p1['z'],
                p2['x'], p2['y'], p2['z'],
                extruding, color, feed_rate
            )
            current_layer.add_segment(segment)

            if extruding:
                self._update_bbox(p2['x'], p2['y'], p2['z'])
                distance = ((p2['x'] - p1['x'])**2 +
                           (p2['y'] - p1['y'])**2 +
                           (p2['z'] - p1['z'])**2)**0.5
                self.total_extrusion += distance
            else:
                distance = ((p2['x'] - p1['x'])**2 +
                           (p2['y'] - p1['y'])**2 +
                           (p2['z'] - p1['z'])**2)**0.5
                self.total_travel += distance

        def handle_move(args, is_rapid=False):
            nonlocal last_line

            new_line = {
                'x': absolute(last_line['x'], args['x']) if 'x' in args else last_line['x'],
                'y': absolute(last_line['y'], args['y']) if 'y' in args else last_line['y'],
                'z': absolute(last_line['z'], args['z']) if 'z' in args else last_line['z'],
                'e': absolute_e(last_line['e'], args['e']) if 'e' in args else last_line['e'],
                'f': args['f'] if 'f' in args else last_line['f'],
            }

            e_delta = delta_e(last_line['e'], new_line['e'])
            extruding = e_delta > 0.0001

            add_segment(last_line, new_line, extruding, new_line['f'])

            if new_line['f'] > 0:
                self.max_feed_rate = max(self.max_feed_rate, new_line['f'])
                self.min_feed_rate = min(self.min_feed_rate, new_line['f'])

            last_line = new_line

        def handle_g0(args, line_num):
            handle_move(args, is_rapid=True)

        def handle_g1(args, line_num):
            handle_move(args, is_rapid=False)

        def handle_arc(args, line_num, is_clockwise=True):
            nonlocal last_line
            x = absolute(last_line['x'], args['x']) if 'x' in args else last_line['x']
            y = absolute(last_line['y'], args['y']) if 'y' in args else last_line['y']
            z = absolute(last_line['z'], args['z']) if 'z' in args else last_line['z']
            e = absolute_e(last_line['e'], args['e']) if 'e' in args else last_line['e']
            f = args['f'] if 'f' in args else last_line['f']

            i = args['i'] if 'i' in args else 0
            j = args['j'] if 'j' in args else 0
            k = args['k'] if 'k' in args else 0

            center_x = last_line['x'] + i
            center_y = last_line['y'] + j
            center_z = last_line['z'] + k

            start_x, start_y = last_line['x'], last_line['y']
            end_x, end_y = x, y

            radius_x = start_x - center_x
            radius_y = start_y - center_y
            radius = math.sqrt(radius_x**2 + radius_y**2)

            if radius < 1e-6:
                handle_move(args, is_rapid=False)
                return

            start_angle = math.atan2(radius_y, radius_x)
            end_radius_x = end_x - center_x
            end_radius_y = end_y - center_y
            end_angle = math.atan2(end_radius_y, end_radius_x)

            if is_clockwise:
                while end_angle > start_angle:
                    end_angle -= math.pi * 2
            else:
                while end_angle < start_angle:
                    end_angle += math.pi * 2

            angle_diff = end_angle - start_angle
            num_segments = max(8, int(abs(angle_diff) * 16))
            step_angle = angle_diff / num_segments

            prev_point = {'x': start_x, 'y': start_y, 'z': last_line['z'], 'e': last_line['e']}
            e_delta_total = delta_e(last_line['e'], e) if 'e' in args else 0

            for segment_idx in range(1, num_segments + 1):
                angle = start_angle + step_angle * segment_idx
                seg_x = center_x + radius * math.cos(angle)
                seg_y = center_y + radius * math.sin(angle)
                seg_z = last_line['z'] + (z - last_line['z']) * segment_idx / num_segments
                seg_e = last_line['e'] + e_delta_total * segment_idx / num_segments

                seg_point = {'x': seg_x, 'y': seg_y, 'z': seg_z, 'e': seg_e}
                seg_extruding = e_delta_total > 0.0001

                add_segment(prev_point, seg_point, seg_extruding, f)
                prev_point = seg_point

            last_line = {'x': x, 'y': y, 'z': z, 'e': e, 'f': f}

        def handle_g2(args, line_num):
            handle_arc(args, line_num, is_clockwise=True)

        def handle_g3(args, line_num):
            handle_arc(args, line_num, is_clockwise=False)

        def handle_g21(args, line_num):
            pass

        def handle_g90(args, line_num):
            self._relative = False

        def handle_g91(args, line_num):
            self._relative = True

        def handle_g92(args, line_num):
            nonlocal last_line
            if 'x' in args:
                last_line['x'] = args['x']
            if 'y' in args:
                last_line['y'] = args['y']
            if 'z' in args:
                last_line['z'] = args['z']
            if 'e' in args:
                last_line['e'] = args['e']

        def handle_m82(args, line_num):
            self._e_relative = False

        def handle_m83(args, line_num):
            self._e_relative = True

        def handle_m84(args, line_num):
            pass

        def handle_default(args, line_num):
            pass

        handlers = {
            'G0': handle_g0,
            'G1': handle_g1,
            'G2': handle_g2,
            'G3': handle_g3,
            'G20': handle_g21,
            'G21': handle_g21,
            'G90': handle_g90,
            'G91': handle_g91,
            'G92': handle_g92,
            'M82': handle_m82,
            'M83': handle_m83,
            'M84': handle_m84,
            'default': handle_default,
        }

        parser = GCodeParser(handlers)
        parser.parse(gcode)

        self._calculate_center()
        self._calculate_auto_scale()

    def _calculate_center(self):
        if not self.layers:
            self.center = {'x': 0, 'y': 0, 'z': 0}
            return

        min_x = self.bbox['min']['x']
        max_x = self.bbox['max']['x']
        min_y = self.bbox['min']['y']
        max_y = self.bbox['max']['y']
        min_z = self.bbox['min']['z']
        max_z = self.bbox['max']['z']

        self.center = {
            'x': min_x + (max_x - min_x) / 2,
            'y': min_y + (max_y - min_y) / 2,
            'z': min_z + (max_z - min_z) / 2
        }

    def _calculate_auto_scale(self):
        if not self.layers:
            self.scale = 3.0
            return

        size_x = self.bbox['max']['x'] - self.bbox['min']['x']
        size_y = self.bbox['max']['y'] - self.bbox['min']['y']
        size_z = self.bbox['max']['z'] - self.bbox['min']['z']
        max_size = max(size_x, size_y, size_z)

        if max_size > 0:
            self.scale = 100.0 / max_size
        else:
            self.scale = 3.0

    def get_all_segments(self):
        all_segments = []
        for layer in self.layers:
            all_segments.extend(layer.segments)
        return all_segments

    def get_layer_count(self):
        return len(self.layers)

    def get_model_stats(self):
        total_segments = len(self.get_all_segments())
        return {
            'layers': len(self.layers),
            'segments': total_segments,
            'extrusion_distance': round(self.total_extrusion, 2),
            'travel_distance': round(self.total_travel, 2),
            'total_distance': round(self.total_extrusion + self.total_travel, 2),
            'bbox_min': {k: round(v, 2) for k, v in self.bbox['min'].items()},
            'bbox_max': {k: round(v, 2) for k, v in self.bbox['max'].items()},
            'center': {k: round(v, 2) for k, v in self.center.items()} if self.center else None,
            'max_feed_rate': round(self.max_feed_rate, 0) if self.max_feed_rate > 0 else 0,
            'min_feed_rate': round(self.min_feed_rate, 0) if self.min_feed_rate < float('inf') else 0,
        }