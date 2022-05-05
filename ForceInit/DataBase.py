import re
from typing import Set

from CYLog import mylogger

class DummyMACDataBase(object):

    MAC_set: Set[str]

    def __init__(self):
        
        #super().__init__()
        self.MAC_set = self.load_MAC_set()

    def load_MAC_set(self) -> Set[str]:

        MAC_set = set()
        try:
            with open("dummyDB.db", "r") as f:
                for line in f.readlines():
                    l = line.strip().rstrip()
                    if self.is_valid_MAC(l):
                        MAC_set.add(l.upper())
            return MAC_set
        except Exception as e:
            mylogger().critical(str(e))
            raise

    def writeOut(self) -> None:

        try:
            with open("dummyDB.db", "w") as f:
                f.write("\n".join(self.MAC_set))
        except Exception as e:
            mylogger().critical(str(e))
            raise

    def show(self) -> None:

        mylogger().info("DB Check")
        mylogger().debug(self.MAC_set)

    def is_valid_MAC(self, MAC: str) -> bool:

        pattern = r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}"
        if re.fullmatch(pattern, MAC):
            return True
        return False

    def select(self, MAC: str) -> bool:

        if (MAC.upper() in self.MAC_set): 
            return True
        return False

    def append(self, MAC: str) -> bool:

        if (False == self.is_valid_MAC(MAC)):
            return False
        if (self.select(MAC)):
            return False
        self.MAC_set.add(MAC.upper())
        return True

if __name__ == '__main__':
    pass