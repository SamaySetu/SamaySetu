#!/usr/bin/env python3

import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def test_env():
    """Test railway RL environment"""
    try:
        from environment import RailwayEnv
        
        print("Creating environment...")
        env = RailwayEnv()
        
        print(f"✓ Environment created")
        print(f"  - {len(env.stations)} stations")
        print(f"  - {len(env.tracks)} tracks")
        
        # Test reset
        obs = env.reset()
        print(f"✓ Reset successful, obs shape: {obs.shape}")
        print(f"  - {len(env.trains)} trains spawned")
        
        # Test step
        actions = [2] * env.max_trains  # normal speed
        obs, rewards, done, info = env.step(actions)
        print(f"✓ Step successful")
        print(f"  - Total reward: {sum(rewards):.2f}")
        print(f"  - Episode done: {done}")
        
        # Test render
        print(f"✓ Render test:")
        env.render()
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Railway RL Environment")
    print("=" * 40)
    
    if test_env():
        print("=" * 40)
        print("🎉 Environment test passed!")
    else:
        print("=" * 40)
        print("❌ Environment test failed!")
        sys.exit(1)
