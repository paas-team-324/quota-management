import React from 'react';
import Quota from './Quota'

import { Grid, Typography, Select, Button, CircularProgress } from '@material-ui/core';

const create_button_idle = "Create"
const create_button_working = "Creating..."

class NewProject extends React.Component {

    constructor(props) {
        super(props)

        this.state = {
            project_name: "",
            admin_name: "",
            create_button_text: create_button_idle,
            creating: false,
        }

        this.create = this.create.bind(this)
        this.set_project_name = this.set_project_name.bind(this)
        this.set_admin_name = this.set_admin_name.bind(this)
    }

    create() {

        this.setState({
            creating: true,
            create_button_text: create_button_working
        })

        // TODO create project

    }

    set_project_name(name) {

        // TODO regex validation

        if(true) {

            this.setState({
                project_name: name
            })

        }

    }

    set_admin_name(name) {

        // TODO regex validation

        if(true) {

            this.setState({
                admin_name: name
            })

        }

    }

    componentDidMount() {

        // TODO get data from server

    }

    render() {
        return (
            <div>
                <Grid container spacing={3}>
                    <Grid item xs={3}>
                        <Typography gutterBottom>
                            <span style={{ marginRight: "1%" }}>Name:</span>
                            <Select
                                native
                                value={this.state.project_name}
                                onChange={(event) => {
                                    this.set_project_name(event.target.value)
                                }}>
                            </Select>
                        </Typography>
                    </Grid>
                    <Grid item xs={6}>
                        <Typography gutterBottom>
                            <span style={{ marginRight: "1%" }}>Admin:</span>
                            <Select
                                native
                                value={this.state.admin_name}
                                onChange={(event) => {
                                    this.set_admin_name(event.target.value)
                                }}>
                            </Select>
                        </Typography>
                    </Grid>
                    <Grid item xs={3}>
                        <Button
                            size="small"
                            variant="contained"
                            color="primary"
                            component="span"
                            disabled={this.state.creating}
                            fullWidth
                            onClick={() => this.create()}>
                            {this.state.create_button_text}
                        </Button>
                    </Grid>
                </Grid>
            </div>
        )
    }

}

export default NewProject;