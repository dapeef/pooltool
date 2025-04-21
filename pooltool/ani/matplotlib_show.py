import math
from typing import Union

import matplotlib.patches as patches
import matplotlib.transforms as transforms
from matplotlib import pyplot as plt

from pooltool.objects.table.specs import TableType
from pooltool.system.datatypes import MultiSystem, System


class MatPlotLibShow:
    def __init__(self):
        self.top_thickness = 0.15

        # Set some colour values
        self.color_table = "#1ea625"
        self.color_cushion = "#0b5e0f"
        self.color_top = "#5e400b"
        self.color_pocket = "#000000"
        self.color_path = [  # Path colours for different ball states
            "black",  # stationary = 0
            "blue",  # spinning = 1
            "#b3b3b3",  # sliding = 2
            "white",  # rolling = 3
            "green",  # pocketed = 4
        ]

        # Define cushion polarity
        # 0 draws a cushion to the right of the defining line, 1 to the left
        # Clockwise, starting with the left-most side of the top-left pocket sides
        self.cushion_polarity = [0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0]

    def show(
        self,
        shot_or_shots: Union[System, MultiSystem],
    ):
        # multisystem.reset()
        # if isinstance(shot_or_shots, System):
        #     multisystem.append(shot_or_shots)
        # else:
        #     for shot in shot_or_shots:
        #         multisystem.append(shot)
        fig, ax = plt.subplots()

        self.init_dimensions(shot_or_shots.table)
        self.init_plot(ax, shot_or_shots.table)
        self.draw_table(ax, shot_or_shots.table)

        plt.show()

    def init_dimensions(self, table):
        match table.table_type:
            case TableType.BILLIARD:
                self.cushion_thickness = 0.03  # 30cm, for tables without pockets

            case TableType.POCKET | TableType.SNOOKER:
                self.cushion_thickness = 0
                for line in table.cushion_segments.linear.values():
                    self.cushion_thickness = max(
                        [self.cushion_thickness, -line.p1[0], -line.p2[0]]
                    )

            case _:
                raise ValueError(
                    f"Unsupported table type: {table.table_type}. Supported types are: BILLIARD, POCKET, SNOOKER."
                )

        self.padding = self.top_thickness + self.cushion_thickness

        self.view_min = [-self.padding, -self.padding]
        self.view_max = [table.l + self.padding, table.w + self.padding]

    def init_plot(self, ax, table):
        # ax.set_axis_off()
        ax.set_xlim(self.view_min[0], self.view_max[0])
        ax.set_ylim(self.view_min[1], self.view_max[1])
        ax.set_aspect("equal")

    def draw_table(self, ax, table):
        """Draws the pool table—including cushions (linear and circular), pockets and the wooden top (table perimeter) on a matplotlib axes.

        The playing area is defined such that (0, 0) is its lower-left corner,
        and table.l (length) extends along the x‑axis.
        """

        def draw_cushions(ax, table):
            """Draws the cushions on the table."""

            # --- Draw linear cushion segments ---
            for line_info in table.cushion_segments.linear.values():
                # Convert the two endpoints from (row, col) to (x, y)
                x1, y1 = float(line_info.p1[1]), float(line_info.p1[0])
                x2, y2 = float(line_info.p2[1]), float(line_info.p2[0])

                # Compute the vector and its length.
                dx, dy = x2 - x1, y2 - y1
                length = math.hypot(dx, dy)

                # Calculate the base angle from the x-axis (in degrees).
                base_angle = math.degrees(math.atan2(dy, dx))

                # Adjust the angle using the cushion polarity (assumed to be a list
                # where the id (converted to int) indexes into self.cushion_polarity).
                angle = base_angle + self.cushion_polarity[int(line_info.id) - 1] * 180

                # Find the midpoint of the cushion
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2

                # Create a rectangle whose bottom edge (of thickness) is along the cushion.
                # Starting from relative coordinates (-length/2, 0) with width=length and height=cushion_thickness.
                rect = patches.Rectangle(
                    (-length / 2, 0),
                    length,
                    self.cushion_thickness,
                    facecolor=self.color_cushion,
                    edgecolor=self.color_cushion,
                )

                # Create an affine transform to rotate about (0,0) then translate to the midpoint.
                trans = transforms.Affine2D().rotate_deg(angle).translate(mid_x, mid_y)
                rect.set_transform(trans + ax.transData)
                ax.add_patch(rect)

            # --- Draw circular cushion segments ---
            for circ_info in table.cushion_segments.circular.values():
                # Convert center from (row, col) to (x, y)
                cx, cy = float(circ_info.center[1]), float(circ_info.center[0])
                circle = patches.Circle(
                    (cx, cy),
                    circ_info.radius,
                    facecolor=self.color_cushion,
                    edgecolor=self.color_cushion,
                )
                ax.add_patch(circle)

        def draw_table_top(ax, table):
            """Draws the wooden top (table perimeter) on the table."""

            # --- Draw the wooden top (table perimeter) ---
            # Playing area is from (0, 0) to (table.l, table.w).

            def draw_top_rectangle(_ax, lower_left, width, height):
                """Helper function to draw a rectangle."""
                _rect = patches.Rectangle(
                    lower_left,
                    width,
                    height,
                    facecolor=self.color_top,
                    edgecolor=self.color_top,
                )
                _ax.add_patch(_rect)

            # Top board: drawn on the top of the playing area.
            draw_top_rectangle(
                ax,
                (self.view_min[0], self.view_max[1] - self.top_thickness),
                self.view_max[0] + self.padding,
                self.top_thickness,
            )

            # Left board: drawn to the left of the playing area (negative x).
            draw_top_rectangle(
                ax,
                (self.view_min[0], self.view_min[1]),
                self.top_thickness,
                self.view_max[1] + self.padding,
            )

            # Right board: drawn to the right of the playing area.
            draw_top_rectangle(
                ax,
                (self.view_max[0] - self.top_thickness, self.view_min[1]),
                self.top_thickness,
                self.view_max[1] + self.padding,
            )

            # Bottom board: drawn below the playing area (negative y).
            draw_top_rectangle(
                ax,
                (self.view_min[0], self.view_min[1]),
                self.view_max[0] + self.padding,
                self.top_thickness,
            )

        def draw_pockets(ax, table):
            """Draws the pockets on the table."""

            # --- Draw pockets ---
            # For each pocket, convert the center coordinate and add a circle
            for pocket in table.pockets.values():
                px, py = float(pocket.center[1]), float(pocket.center[0])
                pocket_patch = patches.Circle(
                    (px, py),
                    pocket.radius,
                    facecolor=self.color_pocket,
                    edgecolor=self.color_pocket,
                )
                ax.add_patch(pocket_patch)

        draw_cushions(ax, table)
        draw_table_top(ax, table)
        draw_pockets(ax, table)
