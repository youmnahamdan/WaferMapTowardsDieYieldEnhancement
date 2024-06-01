from numpy import void


class DieInfo:
    def __init__(self, number, site):
        self.info = None  # Store configuration data
        self.number = number; # Store part id
        self.site = site
        self.test_results = [] # Store test results

    def set_info(self, info):
        self.info = info

    def get_info(self):
        return self.info

    def add_test_result(self, test_result):
        self.test_results.append(test_result)

    def get_test_results(self):
        return self.test_results

    def get_number(self):
        return self.number

    def get_site(self):
        return self.site



