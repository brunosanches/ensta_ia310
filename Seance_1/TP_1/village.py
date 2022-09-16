import math
import random
import uuid
from collections import defaultdict

import mesa
import tornado, tornado.ioloop
from mesa import space
from mesa.batchrunner import BatchRunner, BatchRunnerMP, batch_run
from mesa.time import RandomActivation
from mesa.visualization.ModularVisualization import ModularServer, VisualizationElement, UserSettableParameter
from mesa.visualization.modules import ChartModule

class Village(mesa.Model):

    def __init__(self, n_villagers, n_lycanthropes, n_apothicaires, n_chasseurs):
        mesa.Model.__init__(self)
        self.space = mesa.space.ContinuousSpace(600, 600, False)
        self.schedule = RandomActivation(self)
        self.datacollector = mesa.DataCollector({
            "Humains": lambda m: len([personne for personne in m.schedule.agents
                                      if type(personne) == Villager and
                                      not personne.est_lycanthrope]),

            "Lycanthropes": lambda m: len([personne for personne in m.schedule.agents
                                      if type(personne) == Villager and
                                      personne.est_lycanthrope]),

            "Lycanthropes transformés": lambda m: len([personne for personne in m.schedule.agents
                                      if type(personne) == Villager and
                                      personne.est_lycanthrope and
                                      personne.est_transforme]),

            "Total": lambda m: m.schedule.get_agent_count()
        })

        for _ in range(n_villagers):
            self.schedule.add(Villager(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self, 
                                       False))

        for _ in range(n_lycanthropes):
            self.schedule.add(Villager(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self,
                                       True))

        for _ in range(n_apothicaires):
            self.schedule.add(Cleric(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))

        for _ in range(n_chasseurs):
            self.schedule.add(Hunter(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))

    def step(self):
        self.schedule.step()
        self.datacollector.collect(self)

        if self.schedule.steps >= 1000:
            self.running = False




class ContinuousCanvas(VisualizationElement):
    local_includes = [
        "./js/jquery.js",
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

def distance(x1, y1, x2, y2):
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)


class Villager(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village, est_lycanthrope: bool):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model
        self.est_lycanthrope = est_lycanthrope # Paramètre indicant si le villager est un lycanthrope
        self.est_transforme = False # Les villagers qui sont lycanthropes commences sans êtres transformés

    def portrayal_method(self):
        color = "red" if self.est_lycanthrope else "blue" # Lycanthropes sont affichés en rouge
        r = 6 if self.est_lycanthrope and self.est_transforme else 3 # Lycanthropes transformers ont une taille plus grande
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)

        if self.est_lycanthrope:
            if random.random() < 0.1: # 10% de chance d'un lycanthrope se transformer
                self.est_transforme = True

            if self.est_transforme:
                # Cherche des villager proches
                villager_proches = [personne for personne in self.model.schedule.agents
                                        if type(personne) == Villager and
                                        not personne.est_lycanthrope and
                                        distance(self.pos[0], self.pos[1],
                                                 personne.pos[0], personne.pos[1]) < 40.0]

                # Fait l'attaque
                for villager in villager_proches:
                    villager.est_lycanthrope = True

class Cleric(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model

    def portrayal_method(self):
        color = "green" # Les apothicaires sont affiches en verte
        r = 3
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)

        # Cherche des villager proches qui sont des lycanthropes non tranformées
        lycanthrope_proches = [personne for personne in self.model.schedule.agents
                                if type(personne) == Villager and
                                personne.est_lycanthrope and
                                not personne.est_transforme and
                                distance(self.pos[0], self.pos[1],
                                         personne.pos[0], personne.pos[1]) < 30.0]

        # rechange un lycanthrope en humain
        for lycanthrope in lycanthrope_proches:
            lycanthrope.est_lycanthrope = False

class Hunter(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model

    def portrayal_method(self):
        color = "black" # Les apothicaires sont affiches en verte
        r = 3
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)

        # Cherche des lycanthropes transformes proches
        lycanthrope_proches = [personne for personne in self.model.schedule.agents
                                if type(personne) == Villager and
                                personne.est_lycanthrope and
                                personne.est_transforme and
                                distance(self.pos[0], self.pos[1],
                                         personne.pos[0], personne.pos[1]) < 40.0]

        # tue le lycanthrope
        for lycanthrope in lycanthrope_proches:
            self.model.schedule.remove(lycanthrope)

def run_single_server():
    server = ModularServer(Village,
                           [ContinuousCanvas(), ChartModule([
                               { "Label": "Lycanthropes", "Color": "Blue"},
                               { "Label": "Lycanthropes transformés", "Color": "Red"},
                               { "Label": "Humains", "Color": "Yellow"},
                               { "Label": "Total", "Color": "Green"}
                            ], data_collector_name="datacollector")],
                           "Village",
                           {"n_villagers": UserSettableParameter('slider', 'Villageois sains', 25, 1, 50, 1),
                            "n_lycanthropes": UserSettableParameter('slider', 'Lycanthropes', 5, 1, 50, 1),
                            "n_apothicaires": UserSettableParameter('slider', 'Apothicaires', 1, 0, 50, 1),
                            "n_chasseurs": UserSettableParameter('slider', 'Chasseurs', 2, 0, 50, 1)})
    server.port = 8521
    server.launch()
    tornado.ioloop.IOLoop.current().stop()

def run_batch():
    batch = BatchRunner(Village,
                        variable_parameters={
                            "n_apothicaires": range(0, 6, 1)
                        },
                        fixed_parameters={
                            "n_villagers": 50,
                            "n_lycanthropes": 5,
                            "n_chasseurs": 1,
                        },
                        model_reporters={
                            "Humains": lambda m: len([personne for personne in m.schedule.agents
                                                      if type(personne) == Villager and
                                                      not personne.est_lycanthrope]),

                            "Lycanthropes": lambda m: len([personne for personne in m.schedule.agents
                                                           if type(personne) == Villager and
                                                           personne.est_lycanthrope]),

                            "Lycanthropes transformés": lambda m: len([personne for personne in m.schedule.agents
                                                                       if type(personne) == Villager and
                                                                       personne.est_lycanthrope and
                                                                       personne.est_transforme]),

                            "Total":  lambda m: m.schedule.get_agent_count()
                        })

    batch.run_all()
    df = batch.get_model_vars_dataframe()
    print(df.to_markdown())

def run_batchMP():
    result = batch_run(Village,
              parameters={
                  "n_apothicaires": range(0, 6, 1),
                  "n_villagers": range(25, 50, 5),
                  "n_lycanthropes": range(2, 10, 2),
                  "n_chasseurs": range(0, 6, 1)
              },
              number_processes=None)

    print(result)
    #batch.run_all()
    #df = batch.get_model_vars_dataframe()
    #print(df.to_markdown())

if __name__ == "__main__":
    #run_single_server()
    #run_batch()
    run_batchMP()
