#!/usr/bin/python

import logging
import json

from datetime import datetime
from operator import itemgetter

logger = logging.getLogger('soma')

"""Collect messages and events"""


class SignalsHandler(logging.NullHandler):
    """Python logging handler which emits a signal for every log record"""

    def __init__(self, log_signal):
        logging.NullHandler.__init__()
        self.signal = log_signal

    def handle(self, record):
        self.signal.send(record.name, record)


# For calculating scores
epoch = datetime.utcfromtimestamp(0)
epoch_seconds = lambda dt: (dt - epoch).total_seconds() - 1356048000


def score(star_object):
    import random
    return random.random() * 100 - random.random() * 10


class PageManager():
    def __init__(self):
        with open('layouts.json') as f:
            self.layouts = json.load(f)
        self.screen_size = (12.0, 8.0)

    def auto_layout(self, stars):
        """Return a layout for given stars in a list of css class, star pairs."""
        # Rank stars by score
        stars_ranked = sorted(stars, key=lambda s: s.hot(), reverse=True)

        # Find best layout by filling each one with stars and determining which one
        # gives the best score
        layout_scores = dict()
        for layout in self.layouts:
            print("\nLayout: {}".format(layout['name']))
            layout_scores[layout['name']] = 0

            for i, star_cell in enumerate(layout['stars']):
                if i >= len(stars_ranked):
                    continue
                star = stars_ranked[i]

                cell_score = self._cell_score(star_cell)
                layout_scores[layout['name']] += star.hot() * cell_score
                print("{}\t{}\t{}".format(star, star.hot()*cell_score, cell_score))
            print("Score: {}".format(layout_scores[layout['name']]))

        # Select best layout
        selected_layouts = sorted(
            layout_scores.iteritems(),
            key=itemgetter(1),
            reverse=True)

        if len(selected_layouts) == 0:
            logging.error("No fitting layout found")
            return

        for layout in self.layouts:
            if layout['name'] == selected_layouts[0][0]:
                break

        print("Chosen {}".format(layout))

        # Create list of elements in layout
        page = list()
        for i, star_cell in enumerate(layout['stars']):
            if i >= len(stars_ranked):
                break

            star = stars_ranked[i]

            # CSS class name format
            # col   column at which the css container begins
            # row   row at which it begins
            # w     width of the container
            # h     height of the container
            css_class = "col{} row{} w{} h{}".format(
                star_cell[0],
                star_cell[1],
                star_cell[2],
                star_cell[3])
            page.append([css_class, star])
        return page

    def _cell_score(self, cell):
        """Return a score that describes how valuable a given cell on the screen is.
        Cell on the top left is 1.0, score diminishes to the right and bottom. Bigger
        cells get higher scores, cells off the screen get a 0.0"""
        import math

        # position score
        if cell[0] > self.screen_size[0] or cell[1] > self.screen_size[1]:
            pscore = 0.0
        else:
            score_x = 1.0 if cell[0] == 0 else 1.0 / (1.0 + (cell[0]/self.screen_size[0]))
            score_y = 1.0 if cell[1] == 0 else 1.0 / (1.0 + (cell[1]/self.screen_size[1]))
            pscore = (score_x + score_y)/2.0

        # size score (sigmoid)
        area = cell[2] * cell[3]
        sscore = 1.0 / (1+pow(math.exp(1), -0.1*(area-12.0)))
        return pscore * sscore
