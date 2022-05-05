#! /usr/bin/env python
import logging

class Logger:
    def __init__(self, path: str,
                       Flevel = logging.INFO,
                       clevel = logging.NOTSET):
                       
        ##logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
        self.logger = logging.getLogger(path)
        self.logger.setLevel(logging.DEBUG)
        fmt = logging.Formatter('%(asctime)s.%(msecs)03d [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s','%Y-%m-%d %H:%M:%S')
        
        ##Setting CMD log
        if (clevel != logging.NOTSET):
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            sh.setLevel(clevel)
            self.logger.addHandler(sh)

        ##Setting log file
        if (Flevel != logging.NOTSET):
            fh = logging.FileHandler(path)
            fh.setFormatter(fmt)
            fh.setLevel(Flevel)
            self.logger.addHandler(fh)
 
    def __call__(self):
        return self.logger

mylogger = Logger('CYL.LOG', Flevel = logging.INFO, clevel = logging.DEBUG)
 
if __name__ =='__main__':
    logtest = Logger('test.log', Flevel = logging.INFO, clevel = logging.DEBUG)
    logtest().debug('a debug msg.')
    logtest().info('an info msg.')
    logtest().warning('a warning msg.')
    logtest().error('a error msg.')
    logtest().critical('a critical msg.')