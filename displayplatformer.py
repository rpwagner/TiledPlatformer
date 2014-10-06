import pygame
from networking import NetworkGame
import world as wd
import engine as eng
import json
# import ipdb
import os
import random
# os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (x,y)
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600

FPS = pygame.time.Clock()


class ClientPlatformer(NetworkGame):
  def __init__(self, tile, window_coordinates=None):
    """Sets up all the needed client settings"""
    super().__init__(tile)
    if window_coordinates:
      # passed in the location for the window to be at. Used for debugging
      os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (window_coordinates[0], window_coordinates[1])
    pygame.init()
    self.load_time = .01

    self.engine = eng.Engine()
    self.window = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    self.game_objects = {}
    self.background = pygame.image.load("background" + str(self.tile[0]) + str(self.tile[1]) + ".png")
    self.background_rect = self.background.get_rect()

  def init_game(self, data):
    """Get the initial configuration of the game from the master node."""
    for obj_type, obj_list in data.items():
      for game_obj in obj_list:
        constructor = getattr(wd, game_obj['constructor'])
        translate_pos = self.translate_to_local((game_obj['rect'][0], game_obj['rect'][1]))
        # Send Spritesheet also
        if translate_pos != 0:
          self.game_objects[game_obj['id']] = constructor(translate_pos[0], translate_pos[1],
                                                          game_obj['rect'][2], game_obj['rect'][3],
                                                          color=game_obj['color'], obj_id=game_obj['id'])
        else:
          self.game_objects[game_obj['id']] = constructor(game_obj['rect'][0], game_obj['rect'][1],
                                                          game_obj['rect'][2], game_obj['rect'][3],
                                                          color=game_obj['color'], obj_id=game_obj['id'])

          self.game_objects[game_obj['id']].render = False

    # print(self.game_objects)
    return data

  def update(self, data):
    """override this method, only hook needed for the server"""
    if data['state'] == 'play':
      return self.play_state(data)
    elif data['state'] == 'load':
      return self.load_state(data)
    else:
      ipdb.set_trace()

  def clear(self, color=(0, 0, 0)):
    """override this method, only hook needed for the server"""
    self.window.blit(self.background, self.background_rect)
    # self.window.fill(color)

  def load_state(self, data):
    # move every object on screen out
    obj_on_screen = [game_obj for game_obj in self.game_objects.values() if game_obj.render]
    print(obj_on_screen)
    end_points = {}
    distance_to_move = {}
    step_dict = {}
    steps_total = 30
    for obj in obj_on_screen:
      start_pointx, start_pointy = random.randint(-1900, 1900), random.randint(-500, 200)
      # how much to change by
      dx, dy = (obj.rect.x - start_pointx, obj.rect.y - start_pointy)
      # how much to move at each step
      # Since there is no subpixels with pygame we need to keep track of all 
      # the steps

      step_sizex, step_sizey = (dx / float(steps_total), dy / float(steps_total))
      step_dict[obj] = []
      for i in range(1, steps_total + 1):
        step_dict[obj].append((start_pointx + step_sizex * i, start_pointy + step_sizey * i))

      obj.rect.x, obj.rect.y = (start_pointx, start_pointy)

    for steps in step_dict.values():
      print(steps)

    for i in range(steps_total):
      # draw objects
      self.clear()
      print(obj_on_screen[0])
      print(obj_on_screen[0].rect)
      for game_obj, step in step_dict.items():
        game_obj.draw(self.window)
        new_x_loc, new_y_loc = step_dict[game_obj].pop(0)  # grap the new place
        game_obj.rect.x, game_obj.rect.y = new_x_loc, new_y_loc

      pygame.display.flip()
      FPS.tick(60)

    # FPS.tick(TICK)
    return {'state': 'play'}

  def play_state(self, data):
    # TODO: why am I passing data in here?
    self.clear(eng.Colors.WHITE)
    for packet in data['game_objects']:
      translated_pos = self.translate_to_local(packet['location'])
      if translated_pos != 0:
        # TODO: don't translate here, do it in a better place
        packet['location'] = translated_pos
        self.game_objects[packet['id']].read_packet(packet)
      else:
        self.game_objects[packet['id']].render = False

    # TODO: this is what loop over game dict is for
    for obj_id, game_obj in self.game_objects.items():
      if game_obj.render:
        game_obj.draw(self.window)
    # obj_to_draw = [obj for obj in game_objects.items() if obj.render]
    # self.engine.map_attribute_flat(game_objects, 'draw')
    pygame.display.flip()

    data_struct = {'state': 'play'}
    return data_struct

  # TODO: actually do that.
  def translate_to_local(self, pos):
    """translates the given data to the local node. Wrapper for call to game
    """
    if ((self.tile[0] + 1) * SCREEN_WIDTH > pos[0] >= self.tile[0] * SCREEN_WIDTH and
        (self.tile[1] + 1) * SCREEN_HEIGHT > pos[1] >= self.tile[1] * SCREEN_HEIGHT):
      translated_pos = [pos[0] - self.tile[0] * SCREEN_WIDTH,
                        (self.tile[1]) * SCREEN_HEIGHT + pos[1]]
    else:
      translated_pos = 0
    return translated_pos  # , translated_pos_2)

  def tanslate_to_global(self):
    """tanstlates the data to the global data """
    pass