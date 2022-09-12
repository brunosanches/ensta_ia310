import math
import random
import uuid
from collections import defaultdict

import mesa
import tornado, tornado.ioloop
from mesa import space
from mesa.time import RandomActivation
from mesa.visualization.ModularVisualization import ModularServer, VisualizationElement


class Village(mesa.Model):

    def __init__(self, n_villagers):
        mesa.Model.__init__(self)
        self.space = mesa.space.ContinuousSpace(600, 600, False)
        self.schedule = RandomActivation(self)
        for _ in range(n_villagers):
            self.schedule.add(Villager(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))

    def step(self):
        self.schedule.step()
        if self.schedule.steps >= 1000:
            self.running = False


class ContinuousCanvas(VisualizationElement):
    local_includes = [
        "./js/simple_continuous_canvas.js",
    ]

    def __init__(self, canvas_height=500,
                 canvas_width=500, instantiate=True):
        VisualizationElement.__init__(self)
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        self.identifier = "space-canvas"
        if (instantiate):
            new_element = ("new Simple_Continuous_Module({}, {},'{}')".
                           format(self.canvas_width, self.canvas_height, self.identifier))
            self.js_code = "elements.push(" + new_element + ");"

    def portrayal_method(self, obj):
        return obj.portrayal_method()

    def render(self, model):
        representation = defaultdict(list)
        for obj in model.schedule.agents:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.pos[0] - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.pos[1] - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        return representation


def wander(x, y, speed, model):
    r = random.random() * math.pi * 2
    new_x = max(min(x + math.cos(r) * speed, model.space.x_max), model.space.x_min)
    new_y = max(min(y + math.sin(r) * speed, model.space.y_max), model.space.y_min)

    return new_x, new_y


class Villager(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model

    def portrayal_method(self):
        color = "blue"
        r = 3
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)


def run_single_server():
    server = ModularServer(Village,
                           [ContinuousCanvas()],
                           "Village",
                           {"n_villagers": 25})
    server.port = 8521
    server.launch()
    tornado.ioloop.IOLoop.current().stop()


if __name__ == "__main__":
    run_single_server()
