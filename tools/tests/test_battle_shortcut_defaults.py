"""PC battle defaults must not claim strongest magic is ordinary all-party attack."""
import unittest
from keyboard_test_fixtures import load_planner, SETTINGS
class BattleDefaults(unittest.TestCase):
 def test_distinct_battle_bindings(self):
  text=load_planner().settings(SETTINGS)
  for line in ('strongest = F\n','all_attack = A\n','defend = D\n','throw = W\n'):
   self.assertIn(line,text)
  self.assertNotIn('strongest = F, A',text)
if __name__=='__main__':unittest.main()
