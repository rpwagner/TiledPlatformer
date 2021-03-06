import pygame
import sys
import ipdb
from pygame.locals import *
import world as wd
import engine as eng
import socket
if (sys.version_info > (3, 0)):
  import pickle as pickle
else:
  import cPickle as pickle
import os
import json

network_settings = json.load(open('network_settings.json'))

json_data = open('master_settings.json')

config = json.load(json_data)
# TODO: Maybe it's time to move away from the socket del? That will also require moving off pickling
SOCKET_DEL = config['package_delimeter'].encode('utf-8')
loc = []
FPS = pygame.time.Clock()
TICK = int(config['FPS_TICK'])
GRID_SPACE = [int(config['grid_space'][0]), int(config['grid_space'][1])]
# DISPLAY_SIZE = [600, 600]
DISPLAY_SIZE = {"x": int(config['display_size'][0]), "y": int(config['display_size'][1])}
BEZZEL_SIZE = [30, 30]
DEBUG_CLASSES = []
# DEBUG_CLASSES = [wd.SimpleScenery, wd.Player]


# TODO: have a platformer game class that has all the similar components of the render and 
# master node, and inherit from that?
class MasterPlatformer(object):
  """Class for the platformer head node"""

  def __init__(self, localhosts=1, ip_file=None):
    global config, network_settings
    super(MasterPlatformer, self).__init__()
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0, 0)  # move window to upper left corner
    pygame.init()
    self.game_objects = {}
    self.window = pygame.display.set_mode((60, 60))
    self.engine = eng.Engine()
    self.added = []  # list keeping track of which objects are added
    self.deleted = []  # list keeping track of the ids of objects that are deleted

    self.game_objects = self.load_map()

    # remove none debugin classes if that is what we are doing
    if DEBUG_CLASSES:
      new_game_obj = self.game_objects.copy()
      for obj in self.game_objects.values():
        if type(obj) not in DEBUG_CLASSES:
          print(str(type(obj)))
          del new_game_obj[obj.id]
      self.game_objects = new_game_obj.copy()
    
    if network_settings['localhost'] == "True":
      # Testing one local node, read from the setting to find out which tile we are testing and read
      # move the player to the correct place
      ip_list = ['localhost'] 
      # spawn each player in the corner of the screen
      left_side = DISPLAY_SIZE["x"] * int(network_settings["x"])
      top_side = DISPLAY_SIZE["y"] * int(network_settings["y"])
      game_dict = self.structured_list()  # 
      player1 = game_dict['Player'][0]
      player2 = game_dict['Player'][1]
      player1.rect.x = left_side + 1000
      player2.rect.x = left_side + 900
      player1.rect.y = top_side + 200
      player2.rect.y = top_side + 200
      print(player1.rect)
      print(player2.rect)

    else:  
      # ip_list
      self.ip_list = []
      ips = open('tile-hosts.txt', 'r')
      address = ips.readline().strip()
      ip_list = []
      while address:
          ip_list.append(address)
          address = ips.readline().strip()

    # build the initial data packet
    send_struct = {'game_obj': []}
    for game_obj in self.game_objects.values():
      send_dict = {"rect": [game_obj.rect.x, game_obj.rect.y, game_obj.rect.width,
                            game_obj.rect.height], "id": game_obj.id,
                   "constructor": type(game_obj).__name__}
      if hasattr(game_obj,  "sprite_sheet"):
         send_dict["sprite_sheet"] = game_obj.sprite_sheet
      send_struct['game_obj'].append(send_dict)

    data = pickle.dumps(send_struct, pickle.HIGHEST_PROTOCOL) + '*ET*'.encode('utf-8')

    self.socket_list = []
    for ip in ip_list:
      self.socket_list.append(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
      self.socket_list[-1].connect((ip, 2000))
      self.socket_list[-1].sendall(data)

    for node in self.socket_list:
      self.get_whole_packet(node)

    self.state = 'load'

  def run(self):
    while True:
      if self.state == 'play':
        data, self.state = self.play_frame()
      elif self.state == 'load':
        data, self.state = self.load()
      else:
        ipdb.set_trace()
      FPS.tick(TICK)
      # print(FPS.get_fps())

  def load(self):
    send_struct = {'state': 'load'}
    # clients handle the load state so wait for their response and play the game
    return self.serialize_and_sync(send_struct)

  def play_frame(self):
    game_dict = self.structured_list()  # Structure the game object list to manage easier. n time should be fast
    player1 = game_dict['Player'][0]
    player2 = game_dict['Player'][1]
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        self.quit()
        sys.exit()
      elif event.type == KEYDOWN:
        if event.key == K_ESCAPE:
          self.quit()
          sys.exit()          
        if event.key == K_LEFT:
          player1.move_left()
          player1.escape(1)
        elif event.key == K_RIGHT:
          player1.move_right()
          player1.escape(2)
        elif event.key == K_UP:
          player1.jump()
        elif event.key == K_t:
          player1.throw_data()
        elif event.key == K_a:
          player2.move_left()
          player2.escape(1)
        elif event.key == K_d:
          player2.move_right()
          player2.escape(2)
        elif event.key == K_w:
          player2.jump()
        elif event.key == K_SPACE:
          player1.interact(self.game_objects.values())  # TODO: We are passing in way to much data here, fix it.
      elif event.type == KEYUP:
        if event.key == K_LEFT:
          player1.stop_left()
        elif event.key == K_RIGHT:
          player1.stop_right()
        elif event.key == K_a:
          player2.stop_left()
        elif event.key == K_d:
          player2.stop_right()

    self.engine.physics_simulation(self.game_objects.values(), [wd.SimpleScenery])

    self.engine.map_attribute_flat(self.game_objects.values(), 'update')
    self.engine.map_attribute_flat(self.game_objects.values(), 'animate')

    # update the AI after the players have been updated
    self.engine.map_attribute_flat(game_dict['AI'], 'check_for_leader', game_dict['Player'])

    # update meetings/traps
    self.engine.map_attribute_flat(game_dict['Meeting'], 'check_player', game_dict['Player'])

    # construct packet
    send_struct = {'state': 'play', 'deleted_objs': [], 'added_objs': []}
    if network_settings['localhost']:
      send_struct['localhost'] = self.handle_localhost(game_dict['Player'][0])

    # check for objects that have been created and add them to the dict
    for game_obj in self.added:
      self.game_objects[game_obj.id] = game_obj
      send_struct['added_objs'].append({"rect": [game_obj.rect.x, game_obj.rect.y, game_obj.rect.width,
                                                 game_obj.rect.height], "id": game_obj.id,
                                        "sprite_sheet": game_obj.sprite_sheet,
                                        "constructor": type(game_obj).__name__})

    for game_obj_id in self.deleted:
      send_struct['deleted_objs'].append(game_obj_id)
      del self.game_objects[game_obj_id]

    # clear lists
    self.added = []
    self.deleted = []

    game_objects_packets = []  # accumulator for the build_packet function
    self.engine.map_attribute_flat(game_dict['NetworkedObject'], 'build_packet', game_objects_packets)
    send_struct['game_objects'] = game_objects_packets

    return self.serialize_and_sync(send_struct)

  def structured_list(self):
    """take the game object list and return a dict with the keys for static, AI, and player
    objects. An object can be added to multiple lists if it is multiple things i.e.
    a player is a movable game object"""
    ret_dict = {'AI': [], 'StaticObject': [], 'Player': [], 'MovableGameObject': [],
                'NetworkedObject': [], 'Meeting': []}
    for game_obj in self.game_objects.values():
      if isinstance(game_obj, wd.Player):
        ret_dict['Player'].append(game_obj)
      elif isinstance(game_obj, wd.SimpleScenery):
        ret_dict['StaticObject'].append(game_obj)
      elif isinstance(game_obj, wd.Follower):
        ret_dict['AI'].append(game_obj)
      if isinstance(game_obj, wd.MovableGameObject):
        ret_dict['MovableGameObject'].append(game_obj)
      if isinstance(game_obj, wd.NetworkedObject):
        ret_dict['NetworkedObject'].append(game_obj)
      if isinstance(game_obj, wd.Meeting):
        ret_dict['Meeting'].append(game_obj)
    return ret_dict

  def handle_localhost(self, follow_player):
    """special function used to handle things like switching the screens when playing on one local host"""
    # first, find out which tile player one is in. 
    tile_x = int(follow_player.rect.centerx / DISPLAY_SIZE['x'])
    tile_y = int(follow_player.rect.centery / DISPLAY_SIZE['y'])
    return {'x':tile_x, 'y':tile_y}
    # print(tile_x)
    # print(tile_y)


  def add_to_world(self, game_obj):
    self.game_objects[game_obj.id] = game_obj

  def get_whole_packet(self, sock):
    """ensures that we receive the whole stream of data"""
    data = ''.encode('utf-8')
    while True:
      data += sock.recv(4024)
      split = data.split(SOCKET_DEL)  # split at newline, as per our custom protocol
      if len(split) != 2:  # it should be 2 elements big if it got the whole message
        pass
      else:
        x = pickle.loads(split[0])
        return x

  def serialize_and_sync(self, send_struct):
    """serialize data and send it to the nodes."""
    # serialize the data and send
    data = pickle.dumps(send_struct, pickle.HIGHEST_PROTOCOL) + '*ET*'.encode('utf-8')
    for node in self.socket_list:
      node.sendall(data)

    return_list = []
    for node in self.socket_list:
      return_list.append(self.get_whole_packet(node))
    # TODO: return real data
    return '', 'play'

  def quit(self):
    data = pickle.dumps({'state': 'kill'}, pickle.HIGHEST_PROTOCOL) + '*ET*'.encode('utf-8')
    for node in self.socket_list:
      node.sendall(data)
    time.sleep(2)


  def load_map(self):
    global config
    """this function is stupid as shit. I hope you look back at this and feel 
    bad about how awful you approached this. You deserve to feel bad for writing it 
    like this."""
    # load map
    game_objects = {}

    map_json = self.engine.parse_json(config['global_map_file'])
    asset_json = self.engine.parse_json(config['asset_file'])

    # TODO: abstract this parsing to dynamically call the constructor based on the 
    # attribute (reuse map)
    for key in map_json:
      print (key)
      constructor = getattr(wd, key)
      # try:
      for obj_dict in map_json[key]:
        if key == "Portal":
          self.handle_portal(obj_dict, game_objects)
          continue
        if "tile" in obj_dict:
          # tranlate the x and y coordinates
          x, y = self.translate_to_tile(obj_dict['tile'][0], int(obj_dict['x']),
                                        obj_dict['tile'][1], int(obj_dict['y']))
        else:
          print("nope")
          x, y = int(obj_dict['x']), int(obj_dict['y'])
        if key not in asset_json:
          # "invisible object"
          if issubclass(constructor, wd.Constructor):

            tmp = constructor(x, y, int(obj_dict['width']),
                              int(obj_dict['height']), game=self)
          else:
            tmp = constructor(x, y, int(obj_dict['width']),
                              int(obj_dict['height']))
            

        else:
          tmp = constructor(x, y, int(obj_dict['width']),
                            int(obj_dict['height']), sprite_sheet=asset_json[key])
        game_objects[tmp.id] = tmp
      # except Exception, e:
      #   ipdb.set_trace()
    print(game_objects)
    return game_objects

  def handle_portal(self, game_objects):
    """portals are specail objects that need to be created two at a time and
    have there own setting structure"""
    return

  def translate_to_tile(self, tile_x, pos_x, tile_y, pos_y):
    x = int(tile_x) * DISPLAY_SIZE['x'] + pos_x
    y = int(tile_y) * DISPLAY_SIZE['y'] + pos_y
    print(x, y)
    return x, y

if __name__ == '__main__':
  print(sys.argv)
  if len(sys.argv) != 2:
    game = MasterPlatformer(localhosts=1, ip_file=False)
  else:
    game = MasterPlatformer(localhosts=int(sys.argv[1]))
  game.run()
