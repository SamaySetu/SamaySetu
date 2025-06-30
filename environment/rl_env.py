import gym
import numpy as np
import json
import networkx as nx
from gym import spaces
from typing import Dict, List, Tuple

class Train:
    def __init__(self, id: str, start: str, dest: str):
        self.id = id
        self.pos = start  # current station
        self.dest = dest
        self.speed = 0.0  # km/h
        self.delay = 0.0  # minutes
        self.route = []
        
class Track:
    def __init__(self, start: str, end: str, length: float, speed_limit: float):
        self.start = start
        self.end = end
        self.length = length  # km
        self.limit = speed_limit  # km/h
        self.occupied = False
        self.trains = []

class Station:
    def __init__(self, name: str, platforms: int, importance: float):
        self.name = name
        self.platforms = platforms
        self.importance = importance
        self.occupied = 0  # trains at station
        self.queue = []

class RailwayEnv(gym.Env):
    def __init__(self, data_path: str = "../map/data"):
        super().__init__()
        
        # Load data
        self.stations = self._load_stations(f"{data_path}/stations.json")
        self.tracks = self._load_tracks(f"{data_path}/tracks.json")
        self.graph = self._build_graph()
        
        # Env config
        self.max_trains = 20
        self.max_time = 480  # 8 hours in minutes
        self.time = 0
        
        # RL spaces
        n_stations = len(self.stations)
        self.action_space = spaces.MultiDiscrete([4] * self.max_trains)  # stop/slow/normal/fast
        self.observation_space = spaces.Box(0, 1, (n_stations * 3,))  # pos, speed, delay per train
        
        self.trains = {}
        self.reset()
    
    def _load_stations(self, path: str) -> Dict[str, Station]:
        with open(path, 'r') as f:
            data = json.load(f)
        
        stations = {}
        # Handle different data structures
        if isinstance(data, dict) and 'stations' in data:
            station_list = data['stations'][:100]  # limit for prototype
        elif isinstance(data, list):
            station_list = data[:100]
        else:
            station_list = []
        
        for s in station_list:
            if not isinstance(s, dict):
                continue
            name = s.get('name', 'Unknown')
            importance = s.get('importance_score', 50)
            platforms = max(2, int(importance / 20))
            stations[name] = Station(name, platforms, importance)
        return stations
    
    def _load_tracks(self, path: str) -> Dict[Tuple[str, str], Track]:
        with open(path, 'r') as f:
            data = json.load(f)
        
        tracks = {}
        station_names = set(self.stations.keys())
        
        # Handle different data structures  
        if isinstance(data, dict) and 'tracks' in data:
            track_list = data['tracks'][:200]
        elif isinstance(data, list):
            track_list = data[:200]
        else:
            track_list = []
        
        for t in track_list:
            if not isinstance(t, dict):
                continue
            coords = t.get('coords', [])
            if len(coords) < 2:
                continue
                
            # Find nearest stations to track endpoints
            start_station = self._nearest_station(coords[0])
            end_station = self._nearest_station(coords[-1])
            
            if start_station in station_names and end_station in station_names and start_station != end_station:
                length = self._calc_distance(coords[0], coords[-1])
                speed_limit = t.get('speed_limit', 80)
                tracks[(start_station, end_station)] = Track(start_station, end_station, length, speed_limit)
        
        return tracks
    
    def _nearest_station(self, coord: List[float]) -> str:
        # Simple nearest station lookup - just return first station for prototype
        if self.stations:
            return list(self.stations.keys())[0]
        return "Station1"  # fallback
    
    def _calc_distance(self, coord1: List[float], coord2: List[float]) -> float:
        # Haversine distance
        lat1, lon1 = coord1[0], coord1[1]
        lat2, lon2 = coord2[0], coord2[1]
        return abs(lat1 - lat2) + abs(lon1 - lon2)  # simplified for prototype
    
    def _build_graph(self) -> nx.Graph:
        G = nx.Graph()
        for name, station in self.stations.items():
            G.add_node(name, **station.__dict__)
        
        for (start, end), track in self.tracks.items():
            G.add_edge(start, end, **track.__dict__)
        
        return G
    
    def _spawn_trains(self):
        # Spawn trains between high-importance stations
        important_stations = sorted(self.stations.items(), 
                                  key=lambda x: x[1].importance, reverse=True)[:10]
        
        for i in range(min(self.max_trains, len(important_stations) - 1)):
            start = important_stations[i][0]
            dest = important_stations[i + 1][0]
            train = Train(f"T{i}", start, dest)
            train.route = self._get_route(start, dest)
            self.trains[train.id] = train
    
    def _get_route(self, start: str, dest: str) -> List[str]:
        try:
            return nx.shortest_path(self.graph, start, dest)
        except:
            return [start, dest]
    
    def reset(self):
        self.time = 0
        self.trains = {}
        
        # Reset tracks and stations
        for track in self.tracks.values():
            track.occupied = False
            track.trains = []
        
        for station in self.stations.values():
            station.occupied = 0
            station.queue = []
        
        self._spawn_trains()
        return self._get_obs()
    
    def step(self, actions):
        rewards = {}
        dones = {}
        infos = {}
        
        # Move trains based on actions
        for i, (train_id, train) in enumerate(self.trains.items()):
            if i >= len(actions):
                break
                
            action = actions[i]  # 0=stop, 1=slow, 2=normal, 3=fast
            speed_mult = [0, 0.5, 1.0, 1.5][action]
            
            # Get current track
            if len(train.route) > 1:
                current_track = self.tracks.get((train.pos, train.route[1]))
                if current_track:
                    train.speed = current_track.limit * speed_mult
                    
                    # Check if can move (track not occupied)
                    if not current_track.occupied or len(current_track.trains) < 2:
                        # Move train
                        travel_time = current_track.length / max(train.speed, 1) * 60  # minutes
                        if self.time % travel_time < 1:  # simplified movement
                            train.pos = train.route[1]
                            train.route = train.route[1:]
                    else:
                        # Blocked - add delay
                        train.delay += 1
            
            # Calculate reward
            delay_penalty = -train.delay * 0.1
            dest_bonus = 10 if train.pos == train.dest else 0
            importance_bonus = self.stations[train.pos].importance * 0.01
            
            rewards[train_id] = delay_penalty + dest_bonus + importance_bonus
            dones[train_id] = train.pos == train.dest or self.time >= self.max_time
            infos[train_id] = {"delay": train.delay, "pos": train.pos}
        
        self.time += 1
        
        obs = self._get_obs()
        done = all(dones.values()) or self.time >= self.max_time
        
        return obs, list(rewards.values()), done, infos
    
    def _get_obs(self):
        # Simple observation: train positions, speeds, delays
        obs = []
        station_list = list(self.stations.keys())
        
        for i in range(self.max_trains):
            if i < len(self.trains):
                train = list(self.trains.values())[i]
                pos_idx = station_list.index(train.pos) if train.pos in station_list else 0
                obs.extend([
                    pos_idx / len(station_list),  # normalized position
                    train.speed / 100,  # normalized speed
                    min(train.delay / 60, 1)  # normalized delay
                ])
            else:
                obs.extend([0, 0, 0])
        
        return np.array(obs[:self.observation_space.shape[0]])
    
    def render(self, mode='human'):
        if mode == 'human':
            print(f"Time: {self.time}min")
            for train_id, train in self.trains.items():
                print(f"{train_id}: {train.pos} -> {train.dest}, delay: {train.delay:.1f}min")

# Quick test
if __name__ == "__main__":
    try:
        env = RailwayEnv()
        obs = env.reset()
        print(f"Environment created with {len(env.stations)} stations, {len(env.tracks)} tracks")
        print(f"Observation shape: {obs.shape}")
        
        # Test step
        actions = [2] * env.max_trains  # all trains normal speed
        obs, rewards, done, info = env.step(actions)
        print(f"Step complete. Total reward: {sum(rewards):.2f}")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure railway data files exist in map/data/")
