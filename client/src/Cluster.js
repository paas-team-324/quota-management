import React from 'react';
import UpdateQuota from './UpdateQuota';
import NewProject from './NewProject';
import { TabContext, TabPanel, TabList } from '@material-ui/lab';
import { Paper, Tab } from '@material-ui/core';
import EditIcon from '@material-ui/icons/Edit';
import AddIcon from '@material-ui/icons/Add';

// jsonschema validator
let Validator = require('jsonschema').Validator
const validator = new Validator

class Cluster extends React.Component {

    constructor () {
        super();

        this.state = {
			tab: 0
        };
    };

    componentDidUpdate() {
        console.log("cluster component updated")
    }

    render () {

        return (
            <TabContext value={this.state.tab}>
                <Paper square elevation={2} style={{ marginTop: '1%' }}>
                    <TabList
                        indicatorColor="primary"
                        textColor="primary"
                        variant="fullWidth"
                        onChange={(event, newValue) => {
                            this.setState({
                                tab: newValue
                            })
                        }}
                    >
                        <Tab label="Edit Quota" icon={<EditIcon />} value={0}/>
                        <Tab label="New Project" icon={<AddIcon />} value={1}/>
                    </TabList>
                </Paper>
                <Paper square elevation={2} style={{ marginTop: '1%' }}>
                    <TabPanel value={0}>
                        <UpdateQuota request={this.props.request} addAlert={this.props.addAlert} validator={validator} cluster={this.props.cluster}></UpdateQuota>
                    </TabPanel>
                    <TabPanel value={1}>
                        <NewProject request={this.props.request} addAlert={this.props.addAlert} validator={validator}></NewProject>
                    </TabPanel>
                </Paper>
            </TabContext>
        )

    }

}

export default Cluster;