#!/usr/local/bin/python
"""Main app module
"""

import concurrent.futures
import sys
import time
from threading import Thread

import structlog

import conf
import logs
from behaviour import Behaviour
from conf import Configuration
from exchange import ExchangeInterface
from notification import Notifier


def main():
    """Initializes the application
    """
    # Load settings and create the config object
    config = Configuration()
    settings = config.settings

    # Set up logger
    logs.configure_logging(settings['log_level'], settings['log_mode'])
    logger = structlog.get_logger()

    # Configure and run configured behaviour.
    exchange_interface = ExchangeInterface(config.exchanges)

    if settings['market_pairs']:
        market_pairs = settings['market_pairs']
        logger.info("Found configured markets: %s", market_pairs)
        market_data = exchange_interface.get_exchange_markets(
            markets=market_pairs)
    else:
        logger.info("No configured markets, using all available on exchange.")
        market_data = exchange_interface.get_exchange_markets()

    thread_list = []

    for exchange in market_data:
        for key in market_data[exchange].keys():

            market_data_chunk = dict()
            market_data_chunk[exchange] = {key: market_data[exchange][key]}

            workerName = "Worker-{}-{}".format(exchange, key)

            notifier = Notifier(
                config.notifiers, config.indicators, market_data_chunk)
            behaviour = Behaviour(config, exchange_interface, notifier)

            worker = AnalysisWorker(
                workerName, behaviour, notifier, market_data_chunk, settings, logger)
            thread_list.append(worker)
            worker.daemon = True
            worker.start()
            time.sleep(2)

    logger.info('All workers are running!')

    for worker in thread_list:
        worker.join()


class AnalysisWorker(Thread):

    def __init__(self, threadName, behaviour, notifier, market_data, settings, logger):
        Thread.__init__(self)

        self.threadName = threadName
        self.behaviour = behaviour
        self.notifier = notifier
        self.market_data = market_data
        self.settings = settings
        self.logger = logger

    def run(self):
        while True:
            self.logger.info('Starting %s', self.threadName)
            self.behaviour.run(self.market_data, self.settings['output_mode'])
            self.logger.info("%s sleeping for %s seconds",
                             self.threadName, self.settings['update_interval'])
            time.sleep(self.settings['update_interval'])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
