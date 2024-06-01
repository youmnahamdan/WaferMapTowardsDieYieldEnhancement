import io
import sqlite3
import pandas as pd
import warnings
import time
import numpy as np
from math import sqrt, pow
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt # for data visualization

from sklearn.svm import OneClassSVM
warnings.filterwarnings('ignore')


'''
Tasks:
-> functions syntax

-> Learn how to document tests in report
-> Test on other wafers and adjust hyperparameters
-> Test on scaled data
-> Do a self explaintory multiline comment on each function "explaination  args   returns"
'''

class die_level_prediction_model:
    def __init__(self, db_name, mid, kernal = 'sigmoid' , gamma = 0.001, nu = 0.03):
        self.init_count_df()
        self.connect_to_db(db_name)
        self.load_from_db(mid)  # Load wafer information such as center and die dimentions
        self.calculate_effect_probability()
        self.calculate_local_yield_8()
        #self.scale_data()
        self.svm(kernal, gamma, nu)
        self.load_vis_data('temporary_data')
        self.visualize()
        
        # Close db connection 
        self._cursor.close()
        self._conn.close()
        return
    def init_count_df(self):
        '''
        This function initializes a dataframe to store information regarding die count. 
        The information is necessary for visualization and display purposes.
        
        Args:
        Returns:
        '''
        self.count_df = pd.DataFrame({
            'MasterID': [0],
            'die_count': [0],
            'good_die_count_before': [0],
            'bad_die_count_before':[0],
            'good_die_count_after': [0],
            'bad_die_count_after':[0]
        })

        
    def connect_to_db(self, db_name):
        self._conn = sqlite3.connect(db_name)
        self._cursor = self._conn.cursor()
        return
    
    def load_from_db(self, mid):
        '''
        This function loads wafer centers, die dimentions, and data from the database.
        
        Args:
        Returns:
        '''
        # Load (Center_X, Center_Y) centers of the wafer
        self._cursor.execute('SELECT CenterX , CenterY FROM wafer_config WHERE MasterID = ?', (mid,))
        self.centers = self._cursor.fetchall()[0]  #tuple of centers
        
        # Load (DieWidth, DieHeight) Die dimensions
        self._cursor.execute('SELECT DieWidth, DieHeight FROM wafer_config WHERE MasterID = ?', (mid,))
        self.die_dim = self._cursor.fetchall()[0]  #tuple of die dimensions
        
        # Load die_info table and store in a dataframe
        self.die_data_df = pd.read_sql_query('SELECT * FROM die_info WHERE MasterID = ?', self._conn, params=(mid,))
        
        # Update count_df upon loading data to count dies before prediction
        self.count_df['MasterID'] = mid
        self.count_df['die_count'] = self.die_data_df['Passing'].count()
        print("die count:  ", self.die_data_df['Passing'].count())
        

        self.count_df['bad_die_count_before']  = self.die_data_df['Passing'].value_counts()[0]
        self.count_df['good_die_count_before'] = self.die_data_df['Passing'].value_counts()[1]
        print("counts:  ",self.die_data_df['Passing'].value_counts()[0], self.die_data_df['Passing'].value_counts()[1])
        return 
    
    def calculate_effect_probability(self):
        '''
        This fucntion calculates the propabiility of each neighbor to effect referene die, then store'em in a list.
        
        Args: 
        Returns: effect probability list
        '''
        # Sum of each neighbor's distance from reference die
        x, y = self.die_dim
        total_distance = 4/sqrt(pow(x,2)+pow(y,2)) + 2/x + 2/y
        
        # Weight for left and right neighbors
        weight_l_r = 1/(x/total_distance)
        
        # Weight for south and north neighbors
        weight_s_n = 1/(y/total_distance)
        
        # Weight for corner neighbors
        weight_c = 1/(sqrt(pow(x,2)+pow(y,2))/total_distance)
        
        return [weight_c, weight_s_n, weight_c, weight_l_r, weight_l_r, weight_c, weight_s_n, weight_c]
    
    def calculate_local_yield_8(self):
        print("calculating yield")
        #add a new column "visited" to track visited dies
        self.die_data_df['Visited'] = False

        #add a new column "local_region_fail" to store the number of failed dies in the neighborhood
        self.die_data_df['local_yield'] = 0.0
        
        # Add column to hold the distance from the center of the wafer
        self.die_data_df['distance_from_center'] = 0.0
        
        # Since local yield calculations are irreversable I'll trach the number of doog neighbors
        self.die_data_df['good_neighbor'] = 0
        
        # Number of dies in a neighborhood 
        ith_neighborhood = 8
        
        #9-die-neighborhood: a list that containes the base coordinates of all 8 neighbors
        die_neighborhood = [(-1,1), (0,1),(1,1),(-1,0),(1,0),(-1,-1),(0,-1),(1,-1)]
        
        # Probability of neighbor to effect reference die
        #effect_propability = [0.35, 1, 0.35, 0.79, 0.79, 0.35, 1, 0.35]
        effect_propability = self.calculate_effect_probability()
        for index , record in self.die_data_df.iterrows():
            if not record[-4]:      
                local_yield = 0

                good_neighbors = 0 # a vriable to track faulty neighbors

                die_coords = (record[2], record[3],)

                for i in range(ith_neighborhood):
                    
                    neighbor = tuple(int(item_1 * item_2 + item_3) for item_1 , item_2 , item_3 in zip(die_neighborhood[i],self.die_dim , die_coords))

                    pass_fail = self.die_data_df.loc[(self.die_data_df['DieX'] == neighbor[0]) & (self.die_data_df['DieY'] == neighbor[1]), 'Passing']
                    if not pass_fail.empty:
                        if pass_fail.values[0] == 1:  #if the die is not visited and passes parametric tests 
                            good_neighbors += 1
                            local_yield += effect_propability[i]
                
                self.die_data_df.loc[index, 'Visited'] = True
                
                self.die_data_df.loc[index, 'good_neighbor'] = good_neighbors
                
                self.die_data_df.loc[index, 'distance_from_center'] = sqrt(pow(die_coords[0]-self.centers[0],2)+pow(die_coords[1]-self.centers[1],2))
                
                #insert to local_region_fail column
                self.die_data_df.loc[index, 'local_yield'] =  float(local_yield / good_neighbors) if good_neighbors > 0 else 0
        
        return
    
    def calculate_local_failure_24(self):
        return
    
    def scale_data(self):
        # Transform the dataframe using the fit_transform method
        self.scaled_data = StandardScaler().fit_transform(self.die_data_df)

        # Transform to a dataframe (using original column names)
        self.scaled_data_df = pd.DataFrame(self.scaled_data, columns=self.die_data_df.columns)
        return
    
    def visualize(self):
        self.figures_list = []  # Initialize a list to store figures
        
        # 2D die_count to propability visualization
        plt.figure()
        yield_die_count = self.die_data_df['local_yield'].value_counts()
        ax = yield_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Local Yield')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)
        
        
        # 2D die_count to HW Bin visualization
        plt.figure()
        HWB_die_count = self.die_data_df['HardwareBin'].value_counts()
        ax = HWB_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Hardware Bin')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)


        # 2D die_count to SW Bin visualization
        SWB_die_count = self.die_data_df['SoftwareBin'].value_counts()
        ax = SWB_die_count.plot(kind='barh')
        ax.set_xlabel('Die Count')
        ax.set_ylabel('Software Bin')

        # Save the plot to an in-memory buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        self.figures_list.append(buf)
        
        return

    def svm(self, kernal = 'sigmoid' , gamma = 0.001, nu = 0.03):
        print("in model")
        svm = OneClassSVM(kernel = kernal, gamma = gamma, nu = nu)
        
        # Make prediction
        prediction = svm.fit_predict(self.die_data_df[['good_neighbor','local_yield']])
        
        # Find outliers and extract from original data
        outlier_index = np.where(prediction == -1)
        outliers = self.die_data_df.loc[outlier_index]
        self.num_outliers = len(outliers)
        
        # Mark outliers as faulty
        self.die_data_df.loc[outlier_index[0], 'Passing'] = 0 
        
        # Update count_df after prediction
        self.count_df['bad_die_count_after']  = self.die_data_df['Passing'].value_counts()[0]
        self.count_df['good_die_count_after'] = self.die_data_df['Passing'].value_counts()[1]
        print("counts:  ",self.die_data_df['Passing'].value_counts()[0], self.die_data_df['Passing'].value_counts()[1])
        
    def load_vis_data(self, table_name):
        '''
        This function loads data after prediction to the database.
        '''
        print("in loading")
        # Empty table before using
        self._cursor.execute(f'DELETE FROM {table_name}')
        # Insert DataFrame into SQL table
        self.die_data_df.to_sql(table_name, self._conn, if_exists='replace', index=False)
        return
        
    
def main(db_name, mid, kernal = 'sigmoid' , gamma = 0.001, nu = 0.03):
    model = die_level_prediction_model(db_name, mid, kernal = kernal, gamma = gamma, nu = nu)
    return (model.num_outliers, model.count_df , model.figures_list)

if __name__=="__main__":
    count_df , figure_list = main("database.db", 3)
    print("count_df:  ",count_df)
    print("figure_list:  ",figure_list)